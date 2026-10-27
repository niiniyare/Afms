"""F13: Post Sales Invoices (and Delivery Notes) for a closed Forecourt Shift."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

import frappe
from frappe.utils import flt, get_datetime


def post_credit_invoices(shift) -> list[str]:
	"""Post one Sales Invoice (or Delivery Note) per credit customer.

	Monthly-invoicing mode (D26) posts a Delivery Note instead.
	Returns list of posted docnames.
	"""
	company_settings = frappe.get_cached_doc("Forecourt Company Settings", shift.company)
	monthly = (getattr(company_settings, "credit_invoicing", "") or "") == "Monthly"

	posting_dt = get_datetime(shift.shift_end) - timedelta(minutes=1)
	posting_date = str(posting_dt.date())
	posting_time = posting_dt.strftime("%H:%M:%S")

	by_customer: dict[str, list] = defaultdict(list)
	for row in shift.credit_sales:
		if row.customer:
			by_customer[row.customer].append(row)

	tank_wh = _tank_warehouse_map(shift)
	posted: list[str] = []

	for customer, rows in by_customer.items():
		items = _credit_items(rows, tank_wh, shift)
		if not items:
			continue
		if monthly:
			name = _make_delivery_note(shift, customer, items, posting_date, posting_time)
			for row in rows:
				frappe.db.set_value(
					"Shift Credit Sale", row.name, "delivery_note", name, update_modified=False
				)
		else:
			name = _make_invoice(shift, customer, items, posting_date, posting_time)
			for row in rows:
				frappe.db.set_value(
					"Shift Credit Sale", row.name, "sales_invoice", name, update_modified=False
				)
		posted.append(name)

	return posted


def post_walkin_invoice(shift) -> str:
	"""Post the walk-in Sales Invoice for remaining metered fuel and non-POS items.

	Returns the docname, or empty string if there are no items to invoice.
	"""
	station = frappe.get_cached_doc("Station", shift.station)
	posting_dt = get_datetime(shift.shift_end) - timedelta(minutes=1)
	posting_date = str(posting_dt.date())
	posting_time = posting_dt.strftime("%H:%M:%S")

	tank_wh = _tank_warehouse_map(shift)
	items = _walkin_items(shift, tank_wh, station)
	if not items:
		return ""

	return _make_invoice(shift, station.walk_in_customer, items, posting_date, posting_time)


# ── private helpers ──────────────────────────────────────────────────────────


def _tank_warehouse_map(shift) -> dict[str, str]:
	"""Return {tank_name: warehouse} for tanks referenced in this shift."""
	tanks: set[str] = set()
	for row in shift.meter_readings:
		if row.tank:
			tanks.add(row.tank)
	for row in shift.tank_dips:
		if row.tank:
			tanks.add(row.tank)
	result: dict[str, str] = {}
	for tank in tanks:
		wh = frappe.db.get_value("Fuel Tank", tank, "warehouse")
		if wh:
			result[tank] = wh
	return result


def _nozzle_tank_map(shift) -> dict[str, str]:
	"""Return {nozzle: tank} from shift meter readings."""
	return {row.nozzle: row.tank for row in shift.meter_readings if row.nozzle and row.tank}


def _credit_items(rows: list, tank_wh: dict[str, str], shift) -> list[dict]:
	"""Build item lines for one credit customer's credit sale rows."""
	nozzle_tank = _nozzle_tank_map(shift)
	lines: list[dict] = []
	for row in rows:
		tank = nozzle_tank.get(row.nozzle) if row.nozzle else None
		if not tank and row.item:
			tank = frappe.db.get_value(
				"Fuel Tank",
				{"station": shift.station, "item": row.item, "status": "Active"},
				"name",
			)
		warehouse = tank_wh.get(tank) if tank else None
		if not warehouse and tank:
			warehouse = frappe.db.get_value("Fuel Tank", tank, "warehouse")
		lines.append(
			{
				"item_code": row.item,
				"qty": flt(row.qty, 3),
				"rate": flt(row.rate, 2),
				"warehouse": warehouse,
				"description": row.slip_no or "",
			}
		)
	return lines


def _walkin_items(shift, tank_wh: dict[str, str], station) -> list[dict]:
	"""Build walk-in invoice item lines: remaining metered fuel + non-POS item sales."""
	# Metered net volume per (item, tank)
	metered: dict[tuple[str, str], float] = defaultdict(float)
	for row in shift.meter_readings:
		if row.item and row.tank:
			metered[(row.item, row.tank)] += flt(row.net_volume_l, 3)

	# Credit sold per item (total across all credit customers)
	credit_by_item: dict[str, float] = defaultdict(float)
	for row in shift.credit_sales:
		if row.item:
			credit_by_item[row.item] += flt(row.qty, 3)

	# Total metered per item (for proportional credit allocation across tanks)
	total_metered_by_item: dict[str, float] = defaultdict(float)
	for (item, _tank), vol in metered.items():
		total_metered_by_item[item] += vol

	lines: list[dict] = []

	for (item, tank), vol in metered.items():
		credit_total = credit_by_item.get(item, 0.0)
		total_m = total_metered_by_item.get(item, 0.0)
		if total_m > 0 and credit_total > 0:
			credit_share = flt(credit_total * vol / total_m, 3)
		else:
			credit_share = 0.0
		walkin_qty = flt(vol - credit_share, 3)
		if walkin_qty <= 0:
			continue
		warehouse = tank_wh.get(tank) or frappe.db.get_value("Fuel Tank", tank, "warehouse")
		rate = _price_for_item(shift, item)
		lines.append(
			{
				"item_code": item,
				"qty": walkin_qty,
				"rate": flt(rate, 2),
				"warehouse": warehouse,
			}
		)

	# Non-fuel item sales (skip rows imported from POS)
	for row in shift.item_sales:
		if row.pos_invoice:
			continue
		warehouse = row.warehouse or getattr(station, "shop_warehouse", None)
		lines.append(
			{
				"item_code": row.item,
				"qty": flt(row.qty, 3),
				"rate": flt(row.rate, 2),
				"warehouse": warehouse,
			}
		)

	return lines


def _price_for_item(shift, item: str) -> float:
	for row in shift.prices:
		if row.item == item:
			return flt(row.price, 2)
	return 0.0


def _make_invoice(
	shift,
	customer: str,
	items: list[dict],
	posting_date: str,
	posting_time: str,
) -> str:
	"""Create, submit and return the name of a Sales Invoice."""
	si = frappe.new_doc("Sales Invoice")
	si.company = shift.company
	si.customer = customer
	si.posting_date = posting_date
	si.posting_time = posting_time
	si.set_posting_time = 1
	si.update_stock = 1
	si.fms_forecourt_shift = shift.name
	si.station = shift.station
	for item in items:
		si.append("items", item)
	si.flags.ignore_permissions = True
	si.insert(ignore_permissions=True)
	si.submit()
	return si.name


def _make_delivery_note(
	shift,
	customer: str,
	items: list[dict],
	posting_date: str,
	posting_time: str,
) -> str:
	"""Create, submit and return the name of a Delivery Note."""
	dn = frappe.new_doc("Delivery Note")
	dn.company = shift.company
	dn.customer = customer
	dn.posting_date = posting_date
	dn.posting_time = posting_time
	dn.set_posting_time = 1
	dn.fms_forecourt_shift = shift.name
	dn.station = shift.station
	for item in items:
		dn.append("items", item)
	dn.flags.ignore_permissions = True
	dn.insert(ignore_permissions=True)
	dn.submit()
	return dn.name
