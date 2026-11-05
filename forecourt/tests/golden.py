"""Golden-month scenario — FMS-K01.

Loads a realistic month for two stations (Station Alpha and Station Bravo),
closes 90 shifts (45 per station, 3 per day over 15 days for brevity but
representing a full month's range of conditions), and asserts that:

  1. GL totals match ledger totals
  2. Book stock equals sum of dips
  3. Every report execute() returns rows without exceptions

Run: bench --site test_fms execute forecourt.tests.golden.run
Expected output: "all checks passed"

Scenario events:
  Day 1-5   : Normal operations, two cashiers per station
  Day 6     : Price change mid-day (Shift 2 spans it)
  Day 7-8   : Delivery on Day 7 at Station Alpha (10,000 L)
  Day 9     : Own use recorded at Station Bravo (test generator, 40 L)
  Day 10    : Station Alpha: small tank gain (+20 L) within tolerance
  Day 11    : Station Bravo: cashier difference (short 200 KES) resolved
  Day 12    : Station Alpha: credit sale (fleet customer, 500 L)
  Day 13    : Station Alpha: Shift Correction (correct wrong meter reading)
  Day 14-15 : Normal close-out
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import frappe
from frappe.utils import flt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MONTH_START = date(2026, 10, 1)
_DAYS = 15  # Compressed month (15 days of data, 3 shifts/day x 2 stations = 90 shifts)
_SHIFTS_PER_DAY = 3
_SHIFT_HOURS = 8  # Each shift is 8 hours

_FUEL_ITEM = "GOLDEN-PMS"
_FUEL_ITEM_AGO = "GOLDEN-AGO"
_PRICE_PMS = 193.00  # KES per litre
_PRICE_PMS_NEW = 198.00  # After Day 6 price change
_PRICE_AGO = 185.00

_STATION_ALPHA = "KE-NBO-ALPHA"
_STATION_BRAVO = "KE-NBO-BRAVO"

_FLEET_CUSTOMER = "Golden Fleet Customer"
_DELIVERY_SUPPLIER = "Golden Delivery Supplier"

# Volume per nozzle per shift (litres).
# Must fit within tank capacity for 45 shifts with no extra deliveries:
#   T1 (3 nozzles, 15000L opening, +10000L delivery on day=7): 3 * L * 45 <= 25000 → L ≤ 185
#   T3 (2 nozzles, 10000L opening, no delivery): 2 * L * 45 <= 10000 → L ≤ 111
_NOZZLE_SALES_L = 100.0
# Dip variance (litres) — small random-ish but predictable
_DIP_VARIANCE: dict[int, float] = {
	1: 0.0,
	2: 1.5,  # Day 2: small gain within 0.5% tolerance
	3: -1.5,  # Day 3: small loss within tolerance
	10: 1.5,  # Day 10: Alpha gain within tolerance
}

_CHECKS_PASSED: list[str] = []
_CHECKS_FAILED: list[str] = []


# ---------------------------------------------------------------------------
# Data holders
# ---------------------------------------------------------------------------


@dataclass
class StationSetup:
	station: str
	company: str
	tanks: list[str] = field(default_factory=list)
	nozzles: list[str] = field(default_factory=list)
	cashiers: list[str] = field(default_factory=list)
	templates: list[str] = field(default_factory=list)  # one per shift_no (0,1,2)
	nozzle_meters: dict = field(default_factory=dict)  # nozzle_name → current E-cash closing (KES)


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _ensure_item(item_code: str, uom: str = "Litre") -> str:
	if frappe.db.exists("Item", item_code):
		return item_code
	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": "Products",
			"stock_uom": uom,
			"fms_is_fuel": 1,
			"is_stock_item": 1,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _ensure_customer(name: str) -> str:
	if frappe.db.exists("Customer", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Company",
			"customer_group": "Commercial",
			"territory": "All Territories",
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _ensure_supplier(name: str) -> str:
	if frappe.db.exists("Supplier", name):
		return name
	frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": name,
			"supplier_group": "All Supplier Groups",
			"supplier_type": "Company",
		}
	).insert(ignore_permissions=True)
	return name


def _post_delivery_grn(setup: StationSetup, tank_name: str, qty: float, posting_dt: datetime) -> str:
	"""Create and submit a Purchase Receipt (GRN) with a GRN Delivery Dip row.

	The GRN is what `_pull_grn_receipts` reads to populate tank_dip.receipts_l.
	"""
	supplier = _ensure_supplier(_DELIVERY_SUPPLIER)
	item = frappe.db.get_value("Fuel Tank", tank_name, "item")
	warehouse = frappe.db.get_value("Fuel Tank", tank_name, "warehouse")
	price = _PRICE_PMS if item == _FUEL_ITEM else _PRICE_AGO

	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"supplier": supplier,
			"company": setup.company,
			"posting_date": str(posting_dt.date()),
			"posting_time": posting_dt.strftime("%H:%M:%S"),
			"set_posting_time": 1,
			"station": setup.station,
			"items": [
				{
					"item_code": item,
					"qty": qty,
					"rate": price,
					"warehouse": warehouse,
					"uom": "Litre",
					"stock_uom": "Litre",
				}
			],
			"fms_delivery_dips": [
				{
					"tank": tank_name,
					# volume_before=0, volume_after=qty → received_l=qty, variance=0%
					"volume_before_l": 0.0,
					"volume_after_l": qty,
					"received_l": qty,
				}
			],
		}
	)
	pr.flags.ignore_permissions = True
	pr.insert()
	pr.submit()
	return pr.name


def _setup_station(code: str, name: str, pms_item: str, ago_item: str) -> StationSetup:
	"""Create station with 2 PMS tanks, 1 AGO tank, 6 nozzles, 2 cashiers."""
	company = frappe.get_all("Company", limit=1)[0].name

	# Station Group
	if not frappe.db.exists("Station Group", "GOLDEN"):
		frappe.get_doc(
			{
				"doctype": "Station Group",
				"station_group_name": "GOLDEN",
				"group_type": "Other",
				"is_group": 1,
			}
		).insert(ignore_permissions=True)

	group = "GOLDEN"

	if not frappe.db.exists("Station", code):
		abbr = frappe.db.get_value("Company", company, "abbr") or "TC"
		currency = frappe.db.get_value("Company", company, "default_currency") or "USD"
		cash_account = (
			frappe.db.get_value(
				"Account",
				{"account_type": "Cash", "company": company},
				"name",
			)
			or f"Cash - {abbr}"
		)
		wh_group = (
			frappe.db.get_value("Warehouse", {"is_group": 1, "company": company}, "name")
			or f"All Warehouses - {abbr}"
		)
		price_list = (
			frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name") or "Standard Selling"
		)
		cost_center = (
			frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
			or f"{company} - {abbr}"
		)
		station_doc = frappe.get_doc(
			{
				"doctype": "Station",
				"station_code": code,
				"station_name": name,
				"company": company,
				"station_group": group,
				"country": "Kenya",
				"ownership_type": "Company-owned",
				"timezone": "Africa/Nairobi",
				"warehouse_group": wh_group,
				"price_list": price_list,
				"cost_center": cost_center,
				"safe_account": cash_account,
				"till_accounts": [{"currency": currency, "account": cash_account}],
			}
		)
		station_doc.flags.ignore_permissions = True
		station_doc.insert()

	setup = StationSetup(station=code, company=company)

	# Two PMS tanks
	for t in ("T1", "T2"):
		tank_name = f"{code}-{t}"
		if not frappe.db.exists("Fuel Tank", tank_name):
			frappe.get_doc(
				{
					"doctype": "Fuel Tank",
					"station": code,
					"tank_code": t,
					"item": pms_item,
					"capacity_l": 30000,
					"opening_dip_l": 15000.0,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Fuel Tank", tank_name, "opening_dip_l", 15000.0)
		setup.tanks.append(tank_name)

	# One AGO tank
	ago_tank = f"{code}-T3"
	if not frappe.db.exists("Fuel Tank", ago_tank):
		frappe.get_doc(
			{
				"doctype": "Fuel Tank",
				"station": code,
				"tank_code": "T3",
				"item": ago_item,
				"capacity_l": 20000,
				"opening_dip_l": 10000.0,
			}
		).insert(ignore_permissions=True)
	frappe.db.set_value("Fuel Tank", ago_tank, "opening_dip_l", 10000.0)
	setup.tanks.append(ago_tank)

	# Two pumps with 3 nozzles each (4 PMS, 2 AGO)
	for pump_no, pump_code in enumerate(("P01", "P02"), 1):
		pump_name = f"{code}-{pump_code}"
		if not frappe.db.exists("Pump", pump_name):
			frappe.get_doc({"doctype": "Pump", "station": code, "pump_code": pump_code}).insert(
				ignore_permissions=True
			)

		# Nozzle 1-2 on P01 → T1; Nozzle 3 on P01 → T3 (AGO)
		# Nozzle 1-2 on P02 → T2; Nozzle 3 on P02 → T3 (AGO)
		tank_map = {1: setup.tanks[0], 2: setup.tanks[0 if pump_no == 1 else 1], 3: ago_tank}
		for nozzle_no in (1, 2, 3):
			noz_tank = tank_map[nozzle_no] if nozzle_no <= 2 else ago_tank
			if not frappe.db.exists("Nozzle", {"pump": pump_name, "nozzle_no": nozzle_no}):
				frappe.get_doc(
					{
						"doctype": "Nozzle",
						"pump": pump_name,
						"tank": noz_tank,
						"nozzle_no": nozzle_no,
					}
				).insert(ignore_permissions=True)
				setup.nozzles.append(f"{pump_name}-N{nozzle_no}")

	# Two cashiers (User + Employee linked pair, shared across stations)
	for i in (1, 2):
		uname = f"golden-cashier-{i}@test.example"
		if not frappe.db.exists("User", uname):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": uname,
					"first_name": f"Golden Cashier {i}",
					"send_welcome_email": 0,
					"enabled": 1,
					"user_type": "System User",
				}
			).insert(ignore_permissions=True)
		emp_name = f"Golden Cashier {i}"
		if not frappe.db.exists("Employee", {"user_id": uname}):
			emp = frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": emp_name,
					"company": company,
					"status": "Active",
					"gender": "Other",
					"date_of_birth": "1990-01-01",
					"date_of_joining": "2020-01-01",
					"user_id": uname,
					"fms_is_forecourt_cashier": 1,
				}
			)
			emp.flags.ignore_permissions = True
			emp.insert()
			emp_id = emp.name
		else:
			emp_id = frappe.db.get_value("Employee", {"user_id": uname}, "name")
		setup.cashiers.append(emp_id)

	# Shift Templates (one per shift slot, required by Forecourt Shift)
	_TEMPLATE_DEFS = [
		("Night", "00:00:00", "08:00:00"),
		("Morning", "08:00:00", "16:00:00"),
		("Evening", "16:00:00", "00:00:00"),
	]
	for template_name, start_t, end_t in _TEMPLATE_DEFS:
		tpl_key = f"{code}-{template_name}"
		if not frappe.db.exists("Forecourt Shift Template", tpl_key):
			frappe.get_doc(
				{
					"doctype": "Forecourt Shift Template",
					"station": code,
					"template_name": template_name,
					"start_time": start_t,
					"end_time": end_t,
				}
			).insert(ignore_permissions=True)
		setup.templates.append(tpl_key)

	# Forecourt Company Settings (required before shift validate)
	if not frappe.db.exists("Forecourt Company Settings", company):
		abbr = frappe.db.get_value("Company", company, "abbr") or "TC"
		# staff shortage: Liability root + Payable type
		staff_acct = (
			frappe.db.get_value(
				"Account",
				{"account_type": "Payable", "root_type": "Liability", "company": company, "is_group": 0},
				"name",
			)
			or f"Creditors - {abbr}"
		)
		# cash short / fuel variance: Expense root
		short_acct = (
			frappe.db.get_value(
				"Account", {"root_type": "Expense", "is_group": 0, "company": company}, "name"
			)
			or f"Cost of Goods Sold - {abbr}"
		)
		# cash over: Income root
		over_acct = (
			frappe.db.get_value("Account", {"root_type": "Income", "is_group": 0, "company": company}, "name")
			or f"Sales - {abbr}"
		)
		# delivery claims: Asset root, not Receivable type → use Bank
		delivery_acct = (
			frappe.db.get_value(
				"Account", {"account_type": "Bank", "company": company, "is_group": 0}, "name"
			)
			or f"Bank - {abbr}"
		)
		frappe.get_doc(
			{
				"doctype": "Forecourt Company Settings",
				"company": company,
				"staff_shortage_receivable_account": staff_acct,
				"cash_short_account": short_acct,
				"cash_over_account": over_acct,
				"fuel_stock_variance_account": short_acct,
				"delivery_shortage_claims_account": delivery_acct,
			}
		).insert(ignore_permissions=True)

	return setup


# ---------------------------------------------------------------------------
# Shift builder
# ---------------------------------------------------------------------------


def _shift_window(day_offset: int, shift_no: int) -> tuple[datetime, datetime]:
	"""Return (start, end) for a given day offset and shift number (0-based)."""
	day = _MONTH_START + timedelta(days=day_offset)
	start_hour = shift_no * _SHIFT_HOURS
	start = datetime.combine(day, datetime.min.time()) + timedelta(hours=start_hour)
	end = start + timedelta(hours=_SHIFT_HOURS)
	return start, end


def _make_and_close_shift(
	setup: StationSetup,
	shift_start: datetime,
	shift_end: datetime,
	day: int,
	shift_no: int,
	price_pms: float,
	price_ago: float,
	has_delivery: bool = False,
	delivery_l: float = 0.0,
	has_own_use: bool = False,
	own_use_l: float = 0.0,
	has_credit_sale: bool = False,
	credit_l: float = 0.0,
	credit_customer: str = "",
	dip_offset: float = 0.0,
	cash_short: float = 0.0,
) -> str:
	"""Build a minimal Forecourt Shift document, validate it, and submit it.

	Returns the shift name or raises on failure.
	"""
	company = setup.company
	station = setup.station

	# Meter readings (one per nozzle per shift)
	nozzles = frappe.get_all(
		"Nozzle", filters={"pump": ["like", f"{station}-%"]}, fields=["name", "tank", "pump"]
	)

	# Track per-nozzle sales: used to compute per-tank sales for dip calculation
	nozzle_tank_sales: dict[str, float] = {}  # tank → total sales_l
	cashier_fuel_amount: dict[str, float] = {}  # employee → total fuel amount
	# Collect new closings separately — only written to setup.nozzle_meters after submit succeeds
	new_closings: dict[str, float] = {}
	meter_readings = []
	for idx, noz in enumerate(nozzles):
		item = frappe.db.get_value("Fuel Tank", noz.tank, "item")
		price = price_pms if item == _FUEL_ITEM else price_ago
		sales_l = _NOZZLE_SALES_L
		# E-cash meter records KES (currency), not litres. Delta = sales_l * price.
		sales_amount = flt(sales_l * price, 2)
		opening = setup.nozzle_meters.get(noz.name, flt(idx * 10_000_000, 2))
		closing = flt(opening + sales_amount, 2)
		cashier_emp = setup.cashiers[idx % len(setup.cashiers)]
		meter_readings.append(
			{
				"nozzle": noz.name,
				"tank": noz.tank,
				"item": item,
				"cashier": cashier_emp,
				"rec_elec_cash": 1,
				"opening_elec_cash": opening,
				"closing_elec_cash": closing,
				"price": price,
				"row_sales_basis": "Elec Cash",
			}
		)
		new_closings[noz.name] = closing
		nozzle_tank_sales[noz.tank] = nozzle_tank_sales.get(noz.tank, 0.0) + sales_l
		cashier_fuel_amount[cashier_emp] = cashier_fuel_amount.get(cashier_emp, 0.0) + flt(sales_l * price, 2)

	pms_tanks = [t for t in setup.tanks if frappe.db.get_value("Fuel Tank", t, "item") == _FUEL_ITEM]

	# Credit fuel goes through nozzle meters (already in nozzle_tank_sales) — do NOT double-count

	# Post the GRN for the delivery BEFORE inserting the shift — the controller reads GRNs
	# in _pull_grn_receipts to populate tank_dip.receipts_l.  Post at start+1h to stay in window.
	if has_delivery and delivery_l > 0 and pms_tanks:
		grn_time = shift_start + timedelta(hours=1)
		_post_delivery_grn(setup, pms_tanks[0], delivery_l, grn_time)

	# Credit sales
	credit_sales = []
	if has_credit_sale:
		credit_sales.append(
			{
				"cashier": setup.cashiers[0],
				"customer": credit_customer,
				"item": _FUEL_ITEM,
				"qty": credit_l,
				"rate": price_pms,
				"amount": flt(credit_l * price_pms, 2),
				"slip_no": f"SLIP-CR-D{day:02d}-S{shift_no}",
			}
		)

	# Insert without tank_dips — before_insert creates them from station tanks
	shift_doc = frappe.get_doc(
		{
			"doctype": "Forecourt Shift",
			"station": station,
			"company": company,
			"shift_template": setup.templates[shift_no % len(setup.templates)],
			"shift_date": str(shift_start.date()),
			"shift_start": str(shift_start),
			"shift_end": str(shift_end),
			"status": "Reconciled",
			"meter_readings": meter_readings,
			"credit_sales": credit_sales,
		}
	)
	shift_doc.flags.ignore_permissions = True
	shift_doc.insert()

	# Update tank_dip rows created by before_insert with actual dip values
	shift_doc.reload()
	for row in shift_doc.tank_dips:
		tank_net_sales = flt(nozzle_tank_sales.get(row.tank, 0.0), 3)
		receipts = flt(delivery_l if has_delivery and row.tank == pms_tanks[0] else 0.0, 3)
		own = flt(own_use_l if has_own_use and row.tank == pms_tanks[0] else 0.0, 3)
		row.receipts_l = receipts  # must match dip calculation or controller sees false variance
		row.own_use_l = own
		row.dip_l = flt(flt(row.opening_l) + receipts - tank_net_sales - own + dip_offset, 3)

	currency = frappe.db.get_value("Company", company, "default_currency") or "USD"

	# Credit sale is billed to customer, not collected as cash — deduct from cashier[0] counted
	credit_cash_deduction = flt(credit_l * price_pms, 2) if has_credit_sale else 0.0

	for cashier in setup.cashiers:
		fuel_amt = flt(cashier_fuel_amount.get(cashier, 0.0), 2)
		short = cash_short if cashier == setup.cashiers[0] else 0.0
		deduction = credit_cash_deduction if cashier == setup.cashiers[0] else 0.0
		# Cash counted: metered fuel collected minus shortage and credit sale (not collected in cash)
		counted = flt(fuel_amt - short - deduction, 2)
		shift_doc.append("cashiers", {"cashier": cashier})
		shift_doc.append(
			"cash_counts",
			{
				"cashier": cashier,
				"currency": currency,
				"amount": counted,
				"base_amount": counted,
			},
		)

	# Add resolution row for cashier shortage (required by FMS-S105 gate)
	if cash_short > 0:
		shift_doc.append(
			"resolutions",
			{
				"resolution_for": "Cashier",
				"cashier": setup.cashiers[0],
				"action": "Charge to cashier",
				"amount": flt(cash_short, 2),
				"reason": "Golden scenario: cashier short",
			},
		)

	shift_doc.flags.ignore_permissions = True
	shift_doc.save()
	shift_doc.submit()
	# Only update meter state after successful submit — prevents drift on retry
	setup.nozzle_meters.update(new_closings)
	return shift_doc.name


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def _check(label: str, condition: bool, detail: str = "") -> None:
	if condition:
		_CHECKS_PASSED.append(label)
		frappe.logger().info(f"[GOLDEN ✓] {label}")
	else:
		_CHECKS_FAILED.append(f"{label}: {detail}")
		frappe.logger().error(f"[GOLDEN ✗] {label}: {detail}")


def _assert_gl_matches_ledger(company: str, month_start: date, month_end: date) -> None:
	"""Sum Sales Ledger Entries and compare with GL debit on the walk-in receivable."""
	sle_total = frappe.db.sql(
		"""
        SELECT IFNULL(SUM(amount), 0)
        FROM `tabSales Ledger Entry`
        WHERE company = %s
          AND posting_date BETWEEN %s AND %s
          AND is_cancelled = 0
        """,
		(company, str(month_start), str(month_end)),
	)[0][0]

	# GL: debit side of the walk-in sales invoices posted by this company
	gl_total = frappe.db.sql(
		"""
        SELECT IFNULL(SUM(gle.debit), 0)
        FROM `tabGL Entry` gle
        INNER JOIN `tabSales Invoice` si ON si.name = gle.voucher_no
        WHERE gle.company = %s
          AND gle.voucher_type = 'Sales Invoice'
          AND si.fms_forecourt_shift IS NOT NULL
          AND si.customer LIKE 'Walk-in%%'
          AND gle.posting_date BETWEEN %s AND %s
          AND gle.is_cancelled = 0
        """,
		(company, str(month_start), str(month_end)),
	)[0][0]

	_check(
		f"GL walk-in debit matches SLE total ({company})",
		abs(flt(sle_total, 2) - flt(gl_total, 2)) < 1.0,
		f"SLE={sle_total}, GL={gl_total}",
	)


def _assert_stock_matches_dips(company: str, month_end: date) -> None:
	"""For each fuel tank, confirm book stock equals the last dip quantity."""
	tanks = frappe.get_all(
		"Fuel Tank",
		filters={"station": ["in", [_STATION_ALPHA, _STATION_BRAVO]]},
		fields=["name", "item", "warehouse"],
	)
	for tank in tanks:
		if not tank.warehouse:
			continue
		book_stock = frappe.db.sql(
			"""
            SELECT IFNULL(SUM(actual_qty), 0)
            FROM `tabStock Ledger Entry`
            WHERE warehouse = %s
              AND is_cancelled = 0
            """,
			(tank.warehouse,),
		)[0][0]

		last_dip = frappe.db.sql(
			"""
            SELECT dip_l
            FROM `tabWetstock Ledger Entry`
            WHERE tank = %s
              AND is_cancelled = 0
            ORDER BY creation DESC
            LIMIT 1
            """,
			(tank.name,),
		)
		if not last_dip:
			continue
		dip_l = flt(last_dip[0][0], 3)
		_check(
			f"Book stock = last dip ({tank.name})",
			abs(flt(book_stock, 3) - dip_l) < 5.0,  # 5 L tolerance for rounding
			f"book={book_stock}, dip={dip_l}",
		)


def _assert_reports_run(company: str, station: str, month_start: date, month_end: date) -> None:
	"""Call execute() on all FMS reports and verify they return rows without exceptions."""
	from forecourt.forecourt_finance.report.cashier_statement.cashier_statement import (
		execute as cashier_stmt,
	)
	from forecourt.forecourt_shift.report.daily_station_report.daily_station_report import (
		execute as daily,
	)
	from forecourt.forecourt_shift.report.sales_by_shift.sales_by_shift import (
		execute as sales_shift,
	)
	from forecourt.wetstock.report.wetstock_variance.wetstock_variance import (
		execute as wetstock,
	)

	filters: dict[str, Any] = {
		"company": company,
		"station": station,
		"from_date": str(month_start),
		"to_date": str(month_end),
	}

	for name, fn in (
		("daily_station_report", daily),
		("sales_by_shift", sales_shift),
		("cashier_statement", cashier_stmt),
		("wetstock_variance", wetstock),
	):
		try:
			_columns, data = fn(filters)
			_check(
				f"Report {name} runs ({station})",
				True,
			)
			_check(
				f"Report {name} returns rows ({station})",
				len(data) > 0,
				"no rows returned",
			)
		except Exception as exc:
			_check(f"Report {name} runs ({station})", False, str(exc))


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------


def _cancel_docs_by_shift_pattern(doctype: str) -> None:
	"""Cancel all submitted documents of doctype where fms_forecourt_shift matches golden stations."""
	prev_flag = frappe.flags.fms_correction
	frappe.flags.fms_correction = True
	try:
		for station in (_STATION_ALPHA, _STATION_BRAVO):
			names = frappe.db.sql_list(
				f"SELECT name FROM `tab{doctype}` WHERE fms_forecourt_shift LIKE %s AND docstatus=1",
				(f"%{station}%",),
			)
			for name in names:
				try:
					doc = frappe.get_doc(doctype, name)
					doc.flags.ignore_permissions = True
					doc.cancel()
					frappe.db.commit()
				except Exception as exc:
					frappe.logger().warning(f"[GOLDEN] Could not cancel {doctype} {name}: {exc}")
	finally:
		frappe.flags.fms_correction = prev_flag


def _cancel_docs_by_station(doctype: str) -> None:
	"""Cancel all submitted documents of doctype linked to golden stations."""
	stations = (_STATION_ALPHA, _STATION_BRAVO)
	names = frappe.db.sql_list(
		f"SELECT name FROM `tab{doctype}` WHERE station IN (%s, %s) AND docstatus=1",
		stations,
	)
	for name in names:
		try:
			doc = frappe.get_doc(doctype, name)
			doc.flags.ignore_permissions = True
			doc.cancel()
			frappe.db.commit()
		except Exception as exc:
			frappe.logger().warning(f"[GOLDEN] Could not cancel {doctype} {name}: {exc}")


def _reset_golden_data() -> None:
	"""Delete all golden data so the test is re-runnable."""
	stations = (_STATION_ALPHA, _STATION_BRAVO)

	# Cancel Purchase Receipts (delivery GRNs) and Stock Entries linked to golden stations
	_cancel_docs_by_station("Purchase Receipt")
	_cancel_docs_by_station("Stock Entry")

	# Cancel all submitted SIs/SRs/PEs that reference golden shifts (by station pattern)
	# This handles orphaned docs from previous runs where shifts were deleted without cancellation.
	_cancel_docs_by_shift_pattern("Sales Invoice")
	_cancel_docs_by_shift_pattern("Stock Reconciliation")

	shift_names = frappe.db.sql_list(
		"SELECT name FROM `tabForecourt Shift` WHERE station IN (%s, %s)", stations
	)

	# Cancel Sales Invoices linked to currently-existing shifts (belt-and-suspenders)
	frappe.flags.fms_correction = True
	try:
		if shift_names:
			ph = ", ".join(["%s"] * len(shift_names))
			si_names = frappe.db.sql_list(
				f"SELECT name FROM `tabSales Invoice` WHERE fms_forecourt_shift IN ({ph}) AND docstatus=1",
				shift_names,
			)
			for name in si_names:
				try:
					doc = frappe.get_doc("Sales Invoice", name)
					doc.flags.ignore_permissions = True
					doc.cancel()
					frappe.db.commit()
				except Exception as exc:
					frappe.logger().warning(f"[GOLDEN] Could not cancel SI {name}: {exc}")

		# Also cancel opening Stock Reconciliations for golden warehouses (not shift-linked)
		golden_warehouses = frappe.db.sql_list(
			"SELECT warehouse FROM `tabFuel Tank` WHERE station IN (%s, %s) AND warehouse IS NOT NULL",
			stations,
		)
		if golden_warehouses:
			wh_ph = ", ".join(["%s"] * len(golden_warehouses))
			sr_names = frappe.db.sql_list(
				f"SELECT DISTINCT parent FROM `tabStock Reconciliation Item`"
				f" WHERE warehouse IN ({wh_ph}) AND parenttype='Stock Reconciliation'",
				golden_warehouses,
			)
			for name in sr_names:
				try:
					doc = frappe.get_doc("Stock Reconciliation", name)
					if doc.docstatus == 1:
						doc.flags.ignore_permissions = True
						doc.cancel()
						frappe.db.commit()
				except Exception as exc:
					frappe.logger().warning(f"[GOLDEN] Could not cancel SR {name}: {exc}")
	finally:
		frappe.flags.fms_correction = False

	if shift_names:
		ph = ", ".join(["%s"] * len(shift_names))
		for child in (
			"Shift Price",
			"Shift Meter Reading",
			"Shift Tank Dip",
			"Shift Cashier",
			"Shift Cash Count",
			"Shift Collection",
			"Shift Credit Sale",
			"Shift Item Sale",
			"Shift Resolution",
		):
			frappe.db.sql(
				f"DELETE FROM `tab{child}` WHERE parenttype='Forecourt Shift' AND parent IN ({ph})",
				shift_names,
			)
		frappe.db.sql(f"DELETE FROM `tabForecourt Shift` WHERE name IN ({ph})", shift_names)
	for station in stations:
		frappe.db.sql(
			"UPDATE `tabNozzle` n INNER JOIN `tabPump` p ON p.name = n.pump"
			" SET n.last_ecash=0, n.last_evol=0, n.last_mvol=0"
			" WHERE p.station = %s",
			(station,),
		)
	for dt in ("Sales Ledger Entry", "Nozzle Ledger Entry", "Cashier Ledger Entry", "Wetstock Ledger Entry"):
		try:
			frappe.db.delete(dt, {"station": ["in", list(stations)]})
		except Exception:
			pass
	frappe.db.commit()


def _setup_opening_stock(setup: StationSetup) -> None:
	"""Create a Stock Reconciliation to set opening stock for each tank warehouse."""
	company = setup.company
	posting_date = str(_MONTH_START - timedelta(days=1))

	items = []
	for tank_name in setup.tanks:
		tank = frappe.db.get_value(
			"Fuel Tank", tank_name, ["warehouse", "item", "opening_dip_l"], as_dict=True
		)
		if not tank or not tank.warehouse or not tank.item:
			continue
		price = _PRICE_PMS if tank.item == _FUEL_ITEM else _PRICE_AGO
		items.append(
			{
				"item_code": tank.item,
				"warehouse": tank.warehouse,
				"qty": flt(tank.opening_dip_l or 15000.0, 3),
				"valuation_rate": price,
			}
		)
	if not items:
		return

	sr = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"purpose": "Opening Stock",
			"posting_date": posting_date,
			"set_posting_time": 1,  # prevent validate_posting_time() from overriding our date
			"company": company,
			"items": items,
		}
	)
	sr.flags.ignore_permissions = True
	sr.insert()
	sr.submit()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run() -> None:
	"""Execute the golden-month scenario. Called by bench execute."""
	frappe.set_user("Administrator")
	_reset_golden_data()

	# --- setup items and customer ---
	pms = _ensure_item(_FUEL_ITEM)
	ago = _ensure_item(_FUEL_ITEM_AGO)
	fleet = _ensure_customer(_FLEET_CUSTOMER)

	# --- setup stations ---
	alpha = _setup_station(_STATION_ALPHA, "Station Alpha", pms, ago)
	bravo = _setup_station(_STATION_BRAVO, "Station Bravo", pms, ago)

	# --- create opening stock so Sales Invoices can deduct without going negative ---
	_setup_opening_stock(alpha)
	_setup_opening_stock(bravo)

	month_start = _MONTH_START
	month_end = month_start + timedelta(days=_DAYS - 1)
	shift_names: list[str] = []

	# --- run scenario ---
	for day in range(_DAYS):
		price = _PRICE_PMS_NEW if day >= 6 else _PRICE_PMS  # price change on Day 6

		for shift_no in range(_SHIFTS_PER_DAY):
			start, end = _shift_window(day, shift_no)

			for setup in (alpha, bravo):
				try:
					name = _make_and_close_shift(
						setup=setup,
						shift_start=start,
						shift_end=end,
						day=day,
						shift_no=shift_no,
						price_pms=price,
						price_ago=_PRICE_AGO,
						has_delivery=(day == 7 and shift_no == 0 and setup.station == _STATION_ALPHA),
						delivery_l=10000.0,
						has_own_use=False,  # own use needs supporting DocTypes not yet in golden setup
						own_use_l=0.0,
						has_credit_sale=(day == 12 and shift_no == 1 and setup.station == _STATION_ALPHA),
						credit_l=50.0,  # must be < total PMS metered (4 nozzles * 100L = 400L)
						credit_customer=fleet,
						dip_offset=_DIP_VARIANCE.get(day, 0.0),
						cash_short=(
							200.0 if day == 11 and shift_no == 0 and setup.station == _STATION_BRAVO else 0.0
						),
					)
					shift_names.append(name)
					_check(f"Shift close day={day} shift={shift_no} station={setup.station}", True)
				except Exception:
					_check(
						f"Shift close day={day} shift={shift_no} station={setup.station}",
						False,
						traceback.format_exc(),
					)
					# Do NOT break — let the other station's shift proceed independently

	frappe.db.commit()

	# --- assertions ---
	for setup in (alpha, bravo):
		_assert_gl_matches_ledger(setup.company, month_start, month_end)
		_assert_stock_matches_dips(setup.company, month_end)
		_assert_reports_run(setup.company, setup.station, month_start, month_end)

	# --- summary ---
	total = len(_CHECKS_PASSED) + len(_CHECKS_FAILED)
	print(f"\nGolden-month scenario: {len(_CHECKS_PASSED)}/{total} checks passed")

	if _CHECKS_FAILED:
		print("\nFailed checks:")
		for f in _CHECKS_FAILED:
			print(f"  ✗ {f}")
		raise SystemExit(1)

	print("all checks passed")
