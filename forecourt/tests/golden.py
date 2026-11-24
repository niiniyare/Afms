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

import importlib
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
_DIRECTOR = "golden-director@test.example"

_PRICE_CHANGE_DAY = 6
_DELIVERY_DAY = 7
_DELIVERY_L = 10000.0
_RESOLUTION_DAY = 11
_RESOLUTION_KES = 200.0
_CREDIT_DAY = 12
_CREDIT_SHIFT_NO = 1
_CREDIT_L = 50.0
_CORRECTION_DAY = 13
_CORRECTION_PUMP = f"{_STATION_ALPHA}-P01"
_CORRECTION_REDUCTION_KES = 1000.0

_REPORTS = (
	"forecourt.forecourt_finance.report.cash_collection.cash_collection",
	"forecourt.forecourt_finance.report.cash_position_by_station.cash_position_by_station",
	"forecourt.forecourt_finance.report.cashier_performance.cashier_performance",
	"forecourt.forecourt_finance.report.cashier_statement.cashier_statement",
	"forecourt.forecourt_finance.report.clearing_account_ageing.clearing_account_ageing",
	"forecourt.forecourt_finance.report.credit_slips_register.credit_slips_register",
	"forecourt.forecourt_finance.report.payment_mix_matrix.payment_mix_matrix",
	"forecourt.forecourt_finance.report.payment_reconciliation.payment_reconciliation",
	"forecourt.forecourt_finance.report.sales_by_cashier.sales_by_cashier",
	"forecourt.forecourt_finance.report.sales_by_product.sales_by_product",
	"forecourt.forecourt_finance.report.station_comparison.station_comparison",
	"forecourt.forecourt_setup.report.fms_health.fms_health",
	"forecourt.forecourt_shift.report.daily_station_report.daily_station_report",
	"forecourt.forecourt_shift.report.exception_register.exception_register",
	"forecourt.forecourt_shift.report.open_items.open_items",
	"forecourt.forecourt_shift.report.sales_by_shift.sales_by_shift",
	"forecourt.forecourt_shift.report.shift_reconciliation.shift_reconciliation",
	"forecourt.wetstock.report.delivery_variance.delivery_variance",
	"forecourt.wetstock.report.meter_drift.meter_drift",
	"forecourt.wetstock.report.meter_movement.meter_movement",
	"forecourt.wetstock.report.run_out_forecast.run_out_forecast",
	"forecourt.wetstock.report.sales_by_pump_and_nozzle.sales_by_pump_and_nozzle",
	"forecourt.wetstock.report.sales_by_tank.sales_by_tank",
	"forecourt.wetstock.report.tank_stock_movement.tank_stock_movement",
	"forecourt.wetstock.report.tank_stock_position.tank_stock_position",
	"forecourt.wetstock.report.wetstock_variance.wetstock_variance",
)

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

_DV_DAY = 16  # Day offset for dip-variance sub-scenarios (after 15-day main month)
_DV_DIP_OFFSET = 5.05  # Physical surplus vs meter-expected (litres)

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

	from forecourt.forecourt_shift import openings as shift_openings

	prev_shift = shift_openings.latest_submitted_shift(station)

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
		opening = shift_openings.nozzle_openings(noz.name, prev_shift)["opening_elec_cash"]
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
			# Prices must be present so posting/sales.py can find the rate for SI line items.
			# _create_price_rows in before_insert reads from Item Price (which golden doesn't create),
			# so we seed prices here before insert.
			"prices": [
				{
					"item": _FUEL_ITEM,
					"segment_no": 1,
					"price": price_pms,
					"effective_from": str(shift_start),
				},
				{
					"item": _FUEL_ITEM_AGO,
					"segment_no": 1,
					"price": price_ago,
					"effective_from": str(shift_start),
				},
			],
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
				"reason": "Counting error",  # Variance Reason with applies_to_cashier=1
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
	"""Compare attributed SLE totals with total GL debits on all shift-linked SIs.

	SLEs use shift_end.date() so the last shift of the period may land one day past
	month_end (e.g. a midnight-ending shift on day 14 produces SLEs dated day 15).
	Extend the SLE window by one day to capture that edge case.

	Credit-sale SLEs (basis='Exact') overlap with nozzle SLEs (basis='Attributed') —
	the nozzle reading already includes the credit customer's volume — so we sum only
	Attributed SLEs to avoid double-counting.  The GL side therefore includes ALL
	shift-linked SIs (walk-in + credit customers) so both sides equal total nozzle revenue.
	"""
	sle_end = month_end + timedelta(days=1)

	sle_total = frappe.db.sql(
		"""
        SELECT IFNULL(SUM(amount), 0)
        FROM `tabSales Ledger Entry`
        WHERE company = %s
          AND posting_date BETWEEN %s AND %s
          AND basis = 'Attributed'
          AND is_cancelled = 0
          AND (superseded_by IS NULL OR superseded_by = '')
        """,
		(company, str(month_start), str(sle_end)),
	)[0][0]

	# GL: customer receivable side of ALL shift-linked SIs and their credit notes
	gl_total = frappe.db.sql(
		"""
        SELECT IFNULL(SUM(gle.debit - gle.credit), 0)
        FROM `tabGL Entry` gle
        INNER JOIN `tabSales Invoice` si ON si.name = gle.voucher_no
        WHERE gle.company = %s
          AND gle.voucher_type = 'Sales Invoice'
          AND gle.party_type = 'Customer'
          AND si.fms_forecourt_shift IS NOT NULL
          AND gle.posting_date BETWEEN %s AND %s
          AND gle.is_cancelled = 0
        """,
		(company, str(month_start), str(month_end)),
	)[0][0]

	_check(
		f"GL SI debit matches SLE attributed total ({company})",
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
            SELECT IFNULL(actual_qty, 0)
            FROM `tabBin`
            WHERE warehouse = %s
            """,
			(tank.warehouse,),
		)
		book_stock = book_stock[0][0] if book_stock else 0

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


def _report_filters(company: str, station: str, month_start: date, month_end: date) -> dict[str, Any]:
	return {
		"company": company,
		"station": station,
		"date": str(month_start),  # daily_station_report uses "date" (single day)
		"from_date": str(month_start),
		"to_date": str(month_end),
	}


_EMPTY_BY_DESIGN: dict[tuple[str, str], str] = {
	("open_items", _STATION_ALPHA): "all golden shifts submitted, no drafts or open items",
	("open_items", _STATION_BRAVO): "all golden shifts submitted, no drafts or open items",
	("payment_reconciliation", _STATION_ALPHA): "golden scenario imports no provider payments",
	("payment_reconciliation", _STATION_BRAVO): "golden scenario imports no provider payments",
	("delivery_variance", _STATION_BRAVO): "golden scenario delivers only to Station Alpha",
	("credit_slips_register", _STATION_BRAVO): "golden scenario makes credit sales only at Station Alpha",
}


def _assert_reports_run(station: str, filters: dict[str, Any]) -> None:
	"""Call execute() on every FMS report; rows expected unless the scenario makes them empty by design."""
	for path in _REPORTS:
		name = path.rsplit(".", 1)[-1]
		try:
			data = importlib.import_module(path).execute(filters)[1]
		except Exception:
			_check(f"Report {name} runs ({station})", False, traceback.format_exc())
			continue
		_check(f"Report {name} runs ({station})", True)
		reason = _EMPTY_BY_DESIGN.get((name, station))
		if reason:
			_check(
				f"Report {name} empty by design ({station}: {reason})", len(data) == 0, f"rows={len(data)}"
			)
		else:
			_check(f"Report {name} returns rows ({station})", len(data) > 0, "no rows returned")


def _assert_shift_coverage(stations: tuple[str, ...]) -> None:
	expected = _DAYS * _SHIFTS_PER_DAY
	for station in stations:
		count = frappe.db.count("Forecourt Shift", {"station": station, "docstatus": 1})
		_check(f"Submitted shift count = {expected} ({station})", count == expected, f"count={count}")


def _assert_shift_prices(shift_prices: dict[str, float]) -> None:
	"""Each shift's attributed fuel sales must equal litres x the price in force for that shift."""
	rows = frappe.get_all(
		"Sales Ledger Entry",
		filters={
			"forecourt_shift": ["in", list(shift_prices)],
			"basis": "Attributed",
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
		},
		fields=["forecourt_shift", "item", "qty", "amount"],
	)
	totals: dict[tuple[str, str], tuple[float, float]] = {}
	for r in rows:
		qty, amount = totals.get((r.forecourt_shift, r.item), (0.0, 0.0))
		totals[(r.forecourt_shift, r.item)] = (qty + flt(r.qty, 3), amount + flt(r.amount, 2))

	mismatches: list[str] = []
	for shift, pms_price in shift_prices.items():
		for item, price in ((_FUEL_ITEM, pms_price), (_FUEL_ITEM_AGO, _PRICE_AGO)):
			qty, amount = totals.get((shift, item), (0.0, 0.0))
			if qty <= 0 or abs(amount - qty * price) > 0.5:
				mismatches.append(f"{shift} {item}: qty={qty} amount={amount} expected price={price}")
	_check(
		f"Shift sales priced at price in force ({len(shift_prices)} shifts)",
		not mismatches,
		"; ".join(mismatches[:5]),
	)


def _assert_delivery(station: str, delivery_date: date, litres: float) -> None:
	prs = frappe.get_all(
		"Purchase Receipt",
		filters={"station": station, "posting_date": delivery_date, "docstatus": 1},
		pluck="name",
	)
	_check(f"One delivery GRN on {delivery_date} ({station})", len(prs) == 1, f"count={len(prs)}")
	if not prs:
		return

	wle = frappe.get_all(
		"Wetstock Ledger Entry",
		filters={"voucher_type": "Purchase Receipt", "voucher_no": ["in", prs], "is_cancelled": 0},
		fields=["receipt_l"],
	)
	received = sum(flt(r.receipt_l, 3) for r in wle)
	_check(
		f"Delivery litres in wetstock ledger ({station})",
		abs(received - litres) < 0.5,
		f"receipt_l={received}, expected {litres}",
	)

	sle = frappe.get_all(
		"Stock Ledger Entry",
		filters={"voucher_type": "Purchase Receipt", "voucher_no": ["in", prs], "is_cancelled": 0},
		fields=["actual_qty"],
	)
	stock_in = sum(flt(r.actual_qty, 3) for r in sle)
	_check(
		f"Delivery litres in stock ledger ({station})",
		abs(stock_in - litres) < 0.5,
		f"actual_qty={stock_in}, expected {litres}",
	)


def _assert_cashier_resolution(shift: str, amount: float) -> None:
	cle = frappe.get_all(
		"Cashier Ledger Entry",
		filters={
			"forecourt_shift": shift,
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
			"resolution_action": ["is", "set"],
		},
		fields=["resolution_action", "resolution_amount"],
	)
	resolved = sum(flt(r.resolution_amount, 2) for r in cle)
	_check(
		f"Cashier shortage resolution recorded ({shift})",
		abs(resolved - amount) < 0.01,
		f"resolution_amount={resolved}, expected {amount}",
	)

	je_names = frappe.get_all(
		"Journal Entry", filters={"fms_forecourt_shift": shift, "docstatus": 1}, pluck="name"
	)
	staff_lines = (
		frappe.get_all(
			"Journal Entry Account",
			filters={"parent": ["in", je_names], "party_type": "Employee"},
			fields=["debit"],
		)
		if je_names
		else []
	)
	receivable = sum(flt(r.debit, 2) for r in staff_lines)
	_check(
		f"Shortage posted to cashier receivable ({shift})",
		abs(receivable - amount) < 0.01,
		f"employee debit={receivable}, expected {amount}, JEs={je_names}",
	)


def _assert_credit_sale(shift: str, litres: float, price: float) -> None:
	sis = frappe.get_all(
		"Sales Invoice",
		filters={"fms_forecourt_shift": shift, "customer": _FLEET_CUSTOMER, "docstatus": 1},
		fields=["grand_total", "outstanding_amount"],
	)
	expected = flt(litres * price, 2)
	billed = sum(flt(r.grand_total, 2) for r in sis)
	outstanding = sum(flt(r.outstanding_amount, 2) for r in sis)
	_check(
		f"Credit sale invoiced to fleet customer ({shift})",
		bool(sis) and abs(billed - expected) < 0.5,
		f"billed={billed}, expected {expected}, invoices={len(sis)}",
	)
	_check(
		f"Credit sale outstanding on fleet customer ({shift})",
		bool(sis) and abs(outstanding - expected) < 0.5,
		f"outstanding={outstanding}, expected {expected}",
	)


def _ensure_user(email: str, first_name: str) -> None:
	if frappe.db.exists("User", email):
		return
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"send_welcome_email": 0,
			"enabled": 1,
			"user_type": "System User",
			"roles": [{"role": "System Manager"}],
		}
	).insert(ignore_permissions=True)


def _apply_meter_correction(station: str, shift: str) -> None:
	"""Director-approved Shift Correction lowering one nozzle's closing e-cash reading.

	Checks what the correction must leave behind: the approver is the director, the shift
	is Corrected, unaffected nozzles keep their ledger rows, the replacement row carries the
	new closing, and the nozzle's sales ledger matches the corrected meter.
	"""
	nozzle = frappe.db.get_value("Nozzle", {"pump": _CORRECTION_PUMP, "nozzle_no": 1}, "name")
	row = frappe.db.get_value(
		"Shift Meter Reading",
		{"parent": shift, "parenttype": "Forecourt Shift", "nozzle": nozzle},
		["name", "opening_elec_cash", "closing_elec_cash"],
		as_dict=True,
	)
	if not row:
		_check(f"Meter reading row found for correction ({shift})", False, f"nozzle={nozzle}")
		return

	old_closing = flt(row.closing_elec_cash, 2)
	new_closing = flt(old_closing - _CORRECTION_REDUCTION_KES, 2)
	correction = frappe.get_doc(
		{
			"doctype": "Shift Correction",
			"forecourt_shift": shift,
			"station": station,
			"company": frappe.db.get_value("Forecourt Shift", shift, "company"),
			"correction_type": "Meter reading",
			"reason": "Golden scenario: closing e-cash read too high on P01-N1",
			"items": [
				{
					"target_type": "Meter Reading",
					"target_row": row.name,
					"field": "closing_elec_cash",
					"old_value": str(old_closing),
					"new_value": str(new_closing),
				}
			],
		}
	)
	correction.flags.ignore_permissions = True
	correction.insert()

	try:
		correction.submit()
	except Exception as exc:
		_check("Preparer cannot approve own correction (FMS-C501)", "FMS-C501" in str(exc), str(exc))
	else:
		_check("Preparer cannot approve own correction (FMS-C501)", False, "submit succeeded")
		return
	correction.reload()

	_ensure_user(_DIRECTOR, "Golden Director")
	frappe.set_user(_DIRECTOR)
	try:
		correction.flags.ignore_permissions = True
		correction.submit()
	except Exception:
		_check("Director-approved correction submits", False, traceback.format_exc())
		return
	finally:
		frappe.set_user("Administrator")
	_check("Director-approved correction submits", True)

	_check(
		"Correction records the director as approver",
		frappe.db.get_value("Shift Correction", correction.name, "approved_by") == _DIRECTOR,
	)
	status = frappe.db.get_value("Forecourt Shift", shift, "status")
	_check("Corrected shift status is Corrected", status == "Corrected", f"status={status}")

	nozzle_count = frappe.db.count("Nozzle", {"pump": ["like", f"{station}-%"]})
	active_nle = frappe.db.count(
		"Nozzle Ledger Entry",
		{"forecourt_shift": shift, "is_cancelled": 0, "superseded_by": ["is", "not set"]},
	)
	_check(
		f"Unaffected nozzle ledger rows stay active ({shift})",
		active_nle == nozzle_count,
		f"active={active_nle}, expected {nozzle_count}",
	)

	replacement = frappe.get_all(
		"Nozzle Ledger Entry",
		filters={
			"forecourt_shift": shift,
			"correction": correction.name,
			"is_cancelled": 0,
			"nozzle": nozzle,
		},
		fields=["closing_elec_cash"],
	)
	_check(
		f"Replacement nozzle ledger row carries corrected closing ({shift})",
		bool(replacement) and abs(flt(replacement[0].closing_elec_cash, 2) - new_closing) < 0.01,
		f"rows={replacement}, expected closing {new_closing}",
	)

	sales = frappe.get_all(
		"Sales Ledger Entry",
		filters={
			"forecourt_shift": shift,
			"nozzle": nozzle,
			"basis": "Attributed",
			"is_cancelled": 0,
			"superseded_by": ["is", "not set"],
		},
		fields=["amount"],
	)
	sales_total = sum(flt(r.amount, 2) for r in sales)
	expected_sales = flt(new_closing - flt(row.opening_elec_cash, 2), 2)
	_check(
		f"Corrected nozzle sales match corrected meter ({shift})",
		abs(sales_total - expected_sales) < 0.5,
		f"sales={sales_total}, expected {expected_sales}",
	)


# ---------------------------------------------------------------------------
# Dip-variance correction scenario — Decision 1 verification
# ---------------------------------------------------------------------------


def _test_dip_variance_correction(alpha: StationSetup) -> None:
	"""Verify meter correction against a shift that carries an independent dip-based Stock Recon.

	Sub-test A (dip_offset=+5.05, SR expected):
	  1. Original SI deducts metered quantity (update_stock=1).
	  2. Dip-based SR adjusts stock to physical level.
	  3. Correction credit note has update_stock=0.
	  4. Stock after correction = stock after SR (credit note does not move stock).
	  5. Final book stock = last WLE dip_l (mathematical consistency).
	  6. Retry: no duplicate credit notes or SRs.

	Sub-test B (dip_offset=0 → no SR; absent-SR case):
	  7. Correction applies without SR (financial path independent of physical).
	  8. No guard blocks correction due to absent SR.
	"""
	station = alpha.station

	nozzle = frappe.db.get_value("Nozzle", {"pump": _CORRECTION_PUMP, "nozzle_no": 1}, "name")
	if not nozzle:
		_check("DV: nozzle found for DV scenario", False, f"pump={_CORRECTION_PUMP}")
		return

	tank = frappe.db.get_value("Nozzle", nozzle, "tank")
	warehouse = frappe.db.get_value("Fuel Tank", tank, "warehouse") if tank else None
	if not warehouse:
		_check("DV: tank warehouse found for DV scenario", False, f"tank={tank}")
		return

	# ----- Sub-test A: shift with dip_offset > 0 (SR expected) -----

	day_a = _DV_DAY
	shift_start_a = datetime.combine(_MONTH_START + timedelta(days=day_a - 1), datetime.min.time())
	shift_end_a = shift_start_a + timedelta(hours=_SHIFT_HOURS)

	try:
		shift_a = _make_and_close_shift(
			alpha,
			shift_start_a,
			shift_end_a,
			day_a,
			0,
			_PRICE_PMS_NEW,
			_PRICE_AGO,
			dip_offset=_DV_DIP_OFFSET,
		)
	except Exception:
		_check("DV-A: shift with dip_offset=+5.05 closes", False, traceback.format_exc())
		return
	_check("DV-A: shift with dip_offset=+5.05 closes", True)

	# Check 1: original SI has update_stock=1
	si_a = frappe.db.get_value(
		"Sales Invoice",
		{"fms_forecourt_shift": shift_a, "docstatus": 1, "is_return": 0},
		["name", "update_stock"],
		as_dict=True,
	)
	_check(
		"DV-A: original SI update_stock=1",
		bool(si_a) and bool(si_a.update_stock),
		f"si={si_a}",
	)

	# Check 2: SR posted; item qty = last WLE dip_l
	sr_a_rows = frappe.get_all(
		"Stock Reconciliation",
		filters={"fms_forecourt_shift": shift_a, "docstatus": 1},
		fields=["name"],
	)
	_check("DV-A: SR posted (dip_offset creates adjustment)", bool(sr_a_rows), f"shift={shift_a}")

	if sr_a_rows:
		wle_a = frappe.db.sql(
			"SELECT dip_l FROM `tabWetstock Ledger Entry`"
			" WHERE tank=%s AND is_cancelled=0 ORDER BY creation DESC LIMIT 1",
			(tank,),
		)
		last_dip_a = flt(wle_a[0][0], 3) if wle_a else 0.0
		# Join across all SRs for the shift — Alpha has multiple tanks → multiple SR docs
		sr_items_a = frappe.db.sql(
			"SELECT sri.qty FROM `tabStock Reconciliation Item` sri"
			" INNER JOIN `tabStock Reconciliation` sr ON sr.name=sri.parent"
			" WHERE sr.fms_forecourt_shift=%s AND sr.docstatus=1 AND sri.warehouse=%s",
			(shift_a, warehouse),
			as_dict=True,
		)
		sr_qty_a = flt(sr_items_a[0].qty, 3) if sr_items_a else 0.0
		_check(
			"DV-A: SR item qty = last WLE dip_l",
			abs(sr_qty_a - last_dip_a) < 0.01,
			f"sr_qty={sr_qty_a}, dip={last_dip_a}",
		)

	# Capture stock after SR (before correction)
	stock_after_sr_a = flt(frappe.db.get_value("Bin", {"warehouse": warehouse}, "actual_qty") or 0, 3)

	# Apply director-approved correction to shift_a
	nozzle_row_a = frappe.db.get_value(
		"Shift Meter Reading",
		{"parent": shift_a, "parenttype": "Forecourt Shift", "nozzle": nozzle},
		["name", "opening_elec_cash", "closing_elec_cash"],
		as_dict=True,
	)
	if not nozzle_row_a:
		_check("DV-A: meter row found for correction", False, f"shift={shift_a}")
		return

	old_closing_a = flt(nozzle_row_a.closing_elec_cash, 2)
	new_closing_a = flt(old_closing_a - _CORRECTION_REDUCTION_KES, 2)

	corr_a = frappe.get_doc(
		{
			"doctype": "Shift Correction",
			"forecourt_shift": shift_a,
			"station": station,
			"company": frappe.db.get_value("Forecourt Shift", shift_a, "company"),
			"correction_type": "Meter reading",
			"reason": "DV-A: closing e-cash overcounted on P01-N1",
			"items": [
				{
					"target_type": "Meter Reading",
					"target_row": nozzle_row_a.name,
					"field": "closing_elec_cash",
					"old_value": str(old_closing_a),
					"new_value": str(new_closing_a),
				}
			],
		}
	)
	corr_a.flags.ignore_permissions = True
	corr_a.insert()

	try:
		corr_a.submit()
	except Exception as exc:
		_check("DV-A: preparer blocked (FMS-C501)", "FMS-C501" in str(exc), str(exc))
	else:
		_check("DV-A: preparer blocked (FMS-C501)", False, "submit succeeded without director")
		return
	corr_a.reload()

	_ensure_user(_DIRECTOR, "Golden Director")
	frappe.set_user(_DIRECTOR)
	try:
		corr_a.flags.ignore_permissions = True
		corr_a.submit()
	except Exception:
		_check("DV-A: director correction submits", False, traceback.format_exc())
		return
	finally:
		frappe.set_user("Administrator")
	_check("DV-A: director correction submits", True)

	# Check 3: credit note has update_stock=0
	cn_a_rows = frappe.get_all(
		"Sales Invoice",
		filters={"fms_forecourt_shift": shift_a, "is_return": 1, "docstatus": 1},
		fields=["name", "update_stock"],
	)
	_check(
		"DV-A: credit note update_stock=0",
		bool(cn_a_rows) and all(r.update_stock == 0 for r in cn_a_rows),
		f"cn={cn_a_rows}",
	)

	# Check 4: stock after correction = stock after SR (credit note does not move stock)
	stock_after_correction_a = flt(frappe.db.get_value("Bin", {"warehouse": warehouse}, "actual_qty") or 0, 3)
	_check(
		"DV-A: stock unchanged by credit note (update_stock=0)",
		abs(stock_after_correction_a - stock_after_sr_a) < 0.001,
		f"after_sr={stock_after_sr_a}, after_correction={stock_after_correction_a}",
	)

	# Check 5: final book stock = last WLE dip_l
	wle_final_a = frappe.db.sql(
		"SELECT dip_l FROM `tabWetstock Ledger Entry`"
		" WHERE tank=%s AND is_cancelled=0 ORDER BY creation DESC LIMIT 1",
		(tank,),
	)
	final_dip_a = flt(wle_final_a[0][0], 3) if wle_final_a else None
	if final_dip_a is not None:
		_check(
			"DV-A: final book stock = last dip (mathematical consistency)",
			abs(stock_after_correction_a - final_dip_a) < 1.0,
			f"stock={stock_after_correction_a}, dip={final_dip_a}",
		)

	# Check 6: retry — correction applied exactly once; no duplicate credit notes or SRs
	applied_docs_a = frappe.db.get_value("Shift Correction", corr_a.name, "applied_documents") or ""
	_check(
		"DV-A: correction has applied_documents set (applied exactly once)",
		bool(applied_docs_a.strip()),
		f"applied_documents='{applied_docs_a}'",
	)
	_check(
		"DV-A: exactly one credit note for DV-A shift",
		frappe.db.count("Sales Invoice", {"fms_forecourt_shift": shift_a, "is_return": 1, "docstatus": 1})
		== 1,
	)
	_check(
		"DV-A: SR count unchanged after correction (no additional SR from correction)",
		frappe.db.count("Stock Reconciliation", {"fms_forecourt_shift": shift_a, "docstatus": 1})
		== len(sr_a_rows),
		f"expected={len(sr_a_rows)}",
	)

	# ----- Sub-test B: shift with dip_offset=0 (no SR; absent-SR case) -----

	day_b = _DV_DAY + 1
	shift_start_b = datetime.combine(_MONTH_START + timedelta(days=day_b - 1), datetime.min.time())
	shift_end_b = shift_start_b + timedelta(hours=_SHIFT_HOURS)

	try:
		shift_b = _make_and_close_shift(
			alpha,
			shift_start_b,
			shift_end_b,
			day_b,
			0,
			_PRICE_PMS_NEW,
			_PRICE_AGO,
			dip_offset=0.0,
		)
	except Exception:
		_check("DV-B: shift with dip_offset=0 closes", False, traceback.format_exc())
		return
	_check("DV-B: shift with dip_offset=0 closes", True)

	# Confirm no SR posted: dip = book stock exactly → EmptyStockReconciliationItemsError skipped
	sr_b_rows = frappe.get_all(
		"Stock Reconciliation",
		filters={"fms_forecourt_shift": shift_b, "docstatus": 1},
		fields=["name"],
	)
	_check(
		"DV-B: no SR posted when dip equals book stock",
		not sr_b_rows,
		f"unexpected SRs={[r.name for r in sr_b_rows]}",
	)

	# Apply correction to shift_b — establish that correction works without SR
	nozzle_row_b = frappe.db.get_value(
		"Shift Meter Reading",
		{"parent": shift_b, "parenttype": "Forecourt Shift", "nozzle": nozzle},
		["name", "opening_elec_cash", "closing_elec_cash"],
		as_dict=True,
	)
	if not nozzle_row_b:
		_check("DV-B: meter row found", False, f"shift={shift_b}")
		return

	old_closing_b = flt(nozzle_row_b.closing_elec_cash, 2)
	new_closing_b = flt(old_closing_b - _CORRECTION_REDUCTION_KES, 2)
	stock_before_b = flt(frappe.db.get_value("Bin", {"warehouse": warehouse}, "actual_qty") or 0, 3)

	corr_b = frappe.get_doc(
		{
			"doctype": "Shift Correction",
			"forecourt_shift": shift_b,
			"station": station,
			"company": frappe.db.get_value("Forecourt Shift", shift_b, "company"),
			"correction_type": "Meter reading",
			"reason": "DV-B: absent SR — test correction is financial-only",
			"items": [
				{
					"target_type": "Meter Reading",
					"target_row": nozzle_row_b.name,
					"field": "closing_elec_cash",
					"old_value": str(old_closing_b),
					"new_value": str(new_closing_b),
				}
			],
		}
	)
	corr_b.flags.ignore_permissions = True
	corr_b.insert()

	try:
		corr_b.submit()
	except Exception as exc:
		_check("DV-B: preparer blocked (FMS-C501)", "FMS-C501" in str(exc), str(exc))
	else:
		_check("DV-B: preparer blocked (FMS-C501)", False, "submit succeeded without director")
		return
	corr_b.reload()

	frappe.set_user(_DIRECTOR)
	try:
		corr_b.flags.ignore_permissions = True
		corr_b.submit()
	except Exception:
		_check("DV-B: director correction submits without SR", False, traceback.format_exc())
		return
	finally:
		frappe.set_user("Administrator")
	_check("DV-B: director correction submits without SR", True)

	# Credit note posted (financial correction applied regardless of SR)
	cn_b_rows = frappe.get_all(
		"Sales Invoice",
		filters={"fms_forecourt_shift": shift_b, "is_return": 1, "docstatus": 1},
		fields=["name", "update_stock"],
	)
	_check(
		"DV-B: credit note posted without SR (financial path independent of physical)",
		bool(cn_b_rows),
		f"shift={shift_b}",
	)
	_check(
		"DV-B: credit note update_stock=0 (no stock movement when SR absent)",
		bool(cn_b_rows) and all(r.update_stock == 0 for r in cn_b_rows),
		f"cn={cn_b_rows}",
	)

	# Stock unchanged (no SR, no stock movement from credit note → no guard needed)
	stock_after_b = flt(frappe.db.get_value("Bin", {"warehouse": warehouse}, "actual_qty") or 0, 3)
	_check(
		"DV-B: stock unchanged by correction (no SR, update_stock=0 — no guard needed)",
		abs(stock_after_b - stock_before_b) < 0.001,
		f"before={stock_before_b}, after={stock_after_b}",
	)


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
				f"SELECT name FROM `tab{doctype}` WHERE fms_forecourt_shift LIKE %s AND docstatus=1",  # nosec B608
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
		f"SELECT name FROM `tab{doctype}` WHERE station IN (%s, %s) AND docstatus=1",  # nosec B608
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
	_cancel_docs_by_shift_pattern("Journal Entry")

	shift_names = frappe.db.sql_list(
		"SELECT name FROM `tabForecourt Shift` WHERE station IN (%s, %s)", stations
	)

	# Cancel Sales Invoices linked to currently-existing shifts (belt-and-suspenders)
	frappe.flags.fms_correction = True
	try:
		if shift_names:
			ph = ", ".join(["%s"] * len(shift_names))
			si_names = frappe.db.sql_list(
				f"SELECT name FROM `tabSales Invoice` WHERE fms_forecourt_shift IN ({ph}) AND docstatus=1",  # nosec B608
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
				f"SELECT DISTINCT parent FROM `tabStock Reconciliation Item`"  # nosec B608
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

	correction_names = frappe.db.sql_list(
		"SELECT name FROM `tabShift Correction` WHERE station IN (%s, %s)", stations
	)
	if correction_names:
		ph = ", ".join(["%s"] * len(correction_names))
		for child in ("Shift Correction Item", "Shift Resolution"):
			frappe.db.sql(
				f"DELETE FROM `tab{child}` WHERE parenttype='Shift Correction' AND parent IN ({ph})",  # nosec B608
				correction_names,
			)
		frappe.db.sql(f"DELETE FROM `tabShift Correction` WHERE name IN ({ph})", correction_names)  # nosec B608

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
				f"DELETE FROM `tab{child}` WHERE parenttype='Forecourt Shift' AND parent IN ({ph})",  # nosec B608
				shift_names,
			)
		frappe.db.sql(f"DELETE FROM `tabForecourt Shift` WHERE name IN ({ph})", shift_names)  # nosec B608
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
# Company settings helper
# ---------------------------------------------------------------------------


def _ensure_company_settings_currency() -> None:
	"""Update Forecourt Company Settings so all accounts match the company currency.

	ERPNext JE validation rejects entries mixing currencies without multi_currency=1.
	The test company may have USD accounts configured; replace them with same-currency ones.
	"""
	companies = frappe.get_all("Forecourt Company Settings", pluck="name")
	for company in companies:
		ccy = frappe.db.get_value("Company", company, "default_currency") or ""
		if not ccy:
			continue
		cs = frappe.get_doc("Forecourt Company Settings", company)
		changed = False
		for fname in ("staff_shortage_receivable_account", "cash_over_account", "cash_short_account"):
			acct = getattr(cs, fname, None)
			if not acct:
				continue
			acct_ccy = frappe.db.get_value("Account", acct, "account_currency") or ccy
			if acct_ccy != ccy:
				# Find a same-currency account of the same type
				acct_type = frappe.db.get_value("Account", acct, "account_type") or ""
				replacement = frappe.db.get_value(
					"Account",
					{"company": company, "account_type": acct_type, "account_currency": ccy, "is_group": 0},
					"name",
				)
				if replacement:
					setattr(cs, fname, replacement)
					changed = True
		if changed:
			cs.flags.ignore_permissions = True
			cs.save(ignore_permissions=True)


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

	# --- fix company settings to use same-currency accounts (avoids multi-currency JE failure) ---
	_ensure_company_settings_currency()

	# --- setup stations ---
	alpha = _setup_station(_STATION_ALPHA, "Station Alpha", pms, ago)
	bravo = _setup_station(_STATION_BRAVO, "Station Bravo", pms, ago)

	# --- create opening stock so Sales Invoices can deduct without going negative ---
	_setup_opening_stock(alpha)
	_setup_opening_stock(bravo)

	month_start = _MONTH_START
	month_end = month_start + timedelta(days=_DAYS - 1)
	shift_names: list[str] = []
	shift_prices: dict[str, float] = {}
	correction_shift = resolution_shift = credit_shift = ""

	# --- run scenario ---
	for day in range(_DAYS):
		price = _PRICE_PMS_NEW if day >= _PRICE_CHANGE_DAY else _PRICE_PMS

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
						has_delivery=(
							day == _DELIVERY_DAY and shift_no == 0 and setup.station == _STATION_ALPHA
						),
						delivery_l=_DELIVERY_L,
						has_own_use=False,  # own use needs supporting DocTypes not yet in golden setup
						own_use_l=0.0,
						has_credit_sale=(
							day == _CREDIT_DAY
							and shift_no == _CREDIT_SHIFT_NO
							and setup.station == _STATION_ALPHA
						),
						credit_l=_CREDIT_L,  # must be < total PMS metered (4 nozzles * 100L = 400L)
						credit_customer=fleet,
						dip_offset=_DIP_VARIANCE.get(day, 0.0),
						cash_short=(
							_RESOLUTION_KES
							if day == _RESOLUTION_DAY and shift_no == 0 and setup.station == _STATION_BRAVO
							else 0.0
						),
					)
					shift_names.append(name)
					shift_prices[name] = price
					if day == _CORRECTION_DAY and shift_no == 0 and setup.station == _STATION_ALPHA:
						correction_shift = name
					if day == _RESOLUTION_DAY and shift_no == 0 and setup.station == _STATION_BRAVO:
						resolution_shift = name
					if (
						day == _CREDIT_DAY
						and shift_no == _CREDIT_SHIFT_NO
						and setup.station == _STATION_ALPHA
					):
						credit_shift = name
					_check(f"Shift close day={day} shift={shift_no} station={setup.station}", True)
				except Exception:
					_check(
						f"Shift close day={day} shift={shift_no} station={setup.station}",
						False,
						traceback.format_exc(),
					)
					# Do NOT break — let the other station's shift proceed independently

	frappe.db.commit()

	# --- assertions on the closed month ---
	_assert_shift_coverage((_STATION_ALPHA, _STATION_BRAVO))
	_assert_shift_prices(shift_prices)
	_assert_delivery(_STATION_ALPHA, _MONTH_START + timedelta(days=_DELIVERY_DAY), _DELIVERY_L)
	_assert_cashier_resolution(resolution_shift, _RESOLUTION_KES)
	_assert_credit_sale(credit_shift, _CREDIT_L, _PRICE_PMS_NEW)

	# --- director-approved correction, then the same ledger checks must still hold ---
	_apply_meter_correction(_STATION_ALPHA, correction_shift)
	frappe.db.commit()

	for setup in (alpha, bravo):
		_assert_gl_matches_ledger(setup.company, month_start, month_end)
		_assert_stock_matches_dips(setup.company, month_end)
		_assert_reports_run(
			setup.station, _report_filters(setup.company, setup.station, month_start, month_end)
		)

	# --- dip-variance correction scenario (Decision 1 verification) ---
	_test_dip_variance_correction(alpha)
	frappe.db.commit()

	# --- summary ---
	total = len(_CHECKS_PASSED) + len(_CHECKS_FAILED)
	print(f"\nGolden-month scenario: {len(_CHECKS_PASSED)}/{total} checks passed")

	if _CHECKS_FAILED:
		print("\nFailed checks:")
		for f in _CHECKS_FAILED:
			print(f"  ✗ {f}")
		raise SystemExit(1)

	print("all checks passed")
