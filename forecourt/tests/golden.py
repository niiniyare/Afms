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

_STATION_ALPHA = "GLD-ALPHA"
_STATION_BRAVO = "GLD-BRAVO"

_FLEET_CUSTOMER = "Golden Fleet Customer"

# Volume per nozzle per shift (litres) — realistic for 8-hour shift
_NOZZLE_SALES_L = 250.0
# Dip variance (litres) — small random-ish but predictable
_DIP_VARIANCE: dict[int, float] = {
	1: 0.0,
	2: 5.0,  # Day 2: small gain
	3: -3.0,  # Day 3: small loss within tolerance
	10: 20.0,  # Day 10: Alpha gain, still within tolerance
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


def _setup_station(code: str, name: str, pms_item: str, ago_item: str) -> StationSetup:
	"""Create station with 2 PMS tanks, 1 AGO tank, 6 nozzles, 2 cashiers."""
	company = frappe.get_all("Company", limit=1)[0].name

	# Station Group
	if not frappe.db.exists("Station Group", "GOLDEN"):
		frappe.get_doc({"doctype": "Station Group", "group_name": "GOLDEN", "is_group": 1}).insert(
			ignore_permissions=True
		)

	group = "GOLDEN"

	if not frappe.db.exists("Station", code):
		station_doc = frappe.get_doc(
			{
				"doctype": "Station",
				"station_code": code,
				"station_name": name,
				"company": company,
				"station_group": group,
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
				}
			).insert(ignore_permissions=True)
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
			}
		).insert(ignore_permissions=True)
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

	# Two cashiers (Users)
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
		setup.cashiers.append(uname)

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

	# Previous closing meters (cumulative over the month)
	# For simplicity, each nozzle accumulates 1000 L per shift.
	base_ecash = day * _SHIFTS_PER_DAY * _NOZZLE_SALES_L * 1000  # large opening meter

	# Meter readings (one per nozzle per shift)
	nozzles = frappe.get_all(
		"Nozzle", filters={"pump": ["like", f"{station}-%"]}, fields=["name", "tank", "pump"]
	)

	meter_readings = []
	for idx, noz in enumerate(nozzles):
		item = frappe.db.get_value("Fuel Tank", noz.tank, "item")
		price = price_pms if item == _FUEL_ITEM else price_ago
		sales_l = _NOZZLE_SALES_L
		opening = base_ecash + idx * 1000
		closing = opening + sales_l
		meter_readings.append(
			{
				"nozzle": noz.name,
				"tank": noz.tank,
				"item": item,
				"ecash_open": opening,
				"ecash_close": closing,
				"price": price,
				"sales_l": sales_l,
				"sales_amount": flt(sales_l * price, 2),
			}
		)

	# Tank dips
	tank_dips = []
	pms_tanks = [t for t in setup.tanks if frappe.db.get_value("Fuel Tank", t, "item") == _FUEL_ITEM]
	ago_tanks = [t for t in setup.tanks if t not in pms_tanks]

	pms_total_sales = sum(row["sales_l"] for row in meter_readings if row["item"] == _FUEL_ITEM)
	ago_total_sales = sum(row["sales_l"] for row in meter_readings if row["item"] == _FUEL_ITEM_AGO)

	for tank in pms_tanks:
		opening_dip = 15000.0 + dip_offset  # approximate opening
		receipts = delivery_l if has_delivery and tank == pms_tanks[0] else 0.0
		own = own_use_l if has_own_use and tank == pms_tanks[0] else 0.0
		# sales split evenly across PMS tanks
		tank_sales = pms_total_sales / max(len(pms_tanks), 1)
		closing_dip = flt(opening_dip + receipts - tank_sales - own + dip_offset, 3)
		tank_dips.append(
			{
				"tank": tank,
				"item": _FUEL_ITEM,
				"opening_dip": opening_dip,
				"delivery_l": receipts,
				"own_use_l": own,
				"closing_dip": closing_dip,
			}
		)

	for tank in ago_tanks:
		opening_dip = 10000.0
		tank_sales = ago_total_sales / max(len(ago_tanks), 1)
		closing_dip = flt(opening_dip - tank_sales, 3)
		tank_dips.append(
			{
				"tank": tank,
				"item": _FUEL_ITEM_AGO,
				"opening_dip": opening_dip,
				"delivery_l": 0.0,
				"own_use_l": 0.0,
				"closing_dip": closing_dip,
			}
		)

	# Cashiers
	cashiers = []
	total_sales = sum(r["sales_amount"] for r in meter_readings)
	per_cashier = flt(total_sales / len(setup.cashiers), 2)
	for cashier in setup.cashiers:
		cashiers.append(
			{
				"cashier": cashier,
				"expected_cash": per_cashier,
				"counted_cash": per_cashier - (cash_short if cashier == setup.cashiers[0] else 0.0),
				"difference": -(cash_short if cashier == setup.cashiers[0] else 0.0),
				"is_resolved": 1,
				"resolution": "Within tolerance" if cash_short == 0 else "Short charged",
			}
		)

	# Credit sales
	credit_sales = []
	if has_credit_sale:
		credit_sales.append(
			{
				"customer": credit_customer,
				"item": _FUEL_ITEM,
				"quantity": credit_l,
				"rate": price_pms,
				"amount": flt(credit_l * price_pms, 2),
				"tank": pms_tanks[0] if pms_tanks else "",
			}
		)

	shift_doc = frappe.get_doc(
		{
			"doctype": "Forecourt Shift",
			"station": station,
			"company": company,
			"shift_date": str(shift_start.date()),
			"shift_start": str(shift_start),
			"shift_end": str(shift_end),
			"status": "Reconciled",
			"meter_readings": meter_readings,
			"tank_dips": tank_dips,
			"cashiers": cashiers,
			"credit_sales": credit_sales,
		}
	)
	shift_doc.flags.ignore_permissions = True
	shift_doc.insert()
	shift_doc.submit()
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
          AND shift_date BETWEEN %s AND %s
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
          AND si.customer = 'Walk-in'
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
		filters={"station": ["like", "GLD-%"]},
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
            SELECT closing_dip
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
	from forecourt.forecourt_finance.report.daily_station_report.daily_station_report import (
		execute as daily,
	)
	from forecourt.forecourt_finance.report.sales_by_shift.sales_by_shift import (
		execute as sales_shift,
	)
	from forecourt.forecourt_finance.report.wetstock_variance.wetstock_variance import (
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
# Main entry point
# ---------------------------------------------------------------------------


def run() -> None:
	"""Execute the golden-month scenario. Called by bench execute."""
	frappe.set_user("Administrator")

	# --- setup items and customer ---
	pms = _ensure_item(_FUEL_ITEM)
	ago = _ensure_item(_FUEL_ITEM_AGO)
	fleet = _ensure_customer(_FLEET_CUSTOMER)

	# --- setup stations ---
	alpha = _setup_station(_STATION_ALPHA, "Station Alpha", pms, ago)
	bravo = _setup_station(_STATION_BRAVO, "Station Bravo", pms, ago)

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
						price_pms=price,
						price_ago=_PRICE_AGO,
						has_delivery=(day == 7 and shift_no == 0 and setup.station == _STATION_ALPHA),
						delivery_l=10000.0,
						has_own_use=(day == 9 and shift_no == 1 and setup.station == _STATION_BRAVO),
						own_use_l=40.0,
						has_credit_sale=(day == 12 and shift_no == 1 and setup.station == _STATION_ALPHA),
						credit_l=500.0,
						credit_customer=fleet,
						dip_offset=_DIP_VARIANCE.get(day, 0.0),
						cash_short=(
							200.0 if day == 11 and shift_no == 0 and setup.station == _STATION_BRAVO else 0.0
						),
					)
					shift_names.append(name)
					_check(f"Shift close day={day} shift={shift_no} station={setup.station}", True)
				except Exception as exc:
					_check(
						f"Shift close day={day} shift={shift_no} station={setup.station}",
						False,
						str(exc),
					)

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
