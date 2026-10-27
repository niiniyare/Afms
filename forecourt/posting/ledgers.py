"""F15: Write FMS ledger entries (Wetstock, Nozzle, Sales, Cashier)."""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime, today

# ── Shift close: all four ledgers ─────────────────────────────────────────────


def write_shift_wetstock_ledger(shift) -> list[str]:
	"""One Wetstock Ledger Entry per tank dip row (entry_type=Shift)."""
	posting_date = str(get_datetime(shift.shift_end).date())
	cashiers_str = ", ".join(r.cashier for r in shift.cashiers if r.cashier)

	test_by_tank: dict[str, float] = {}
	for row in shift.meter_readings:
		if row.tank:
			test_by_tank[row.tank] = flt(test_by_tank.get(row.tank, 0.0) + flt(row.test_volume_l, 3), 3)

	posted: list[str] = []
	for dip_row in shift.tank_dips:
		if not dip_row.tank:
			continue
		doc = frappe.new_doc("Wetstock Ledger Entry")
		doc.company = shift.company
		doc.station = shift.station
		doc.posting_date = posting_date
		doc.forecourt_shift = shift.name
		doc.voucher_type = "Forecourt Shift"
		doc.voucher_no = shift.name
		doc.entry_type = "Shift"
		doc.tank = dip_row.tank
		doc.item = dip_row.item
		doc.shift_start = shift.shift_start
		doc.shift_end = shift.shift_end
		doc.dip_entry_mode = dip_row.dip_entry_mode
		doc.opening_l = flt(dip_row.opening_l, 3)
		doc.receipt_l = flt(dip_row.receipts_l, 3)
		doc.sales_l = flt(dip_row.sales_l, 3)
		doc.test_l = flt(test_by_tank.get(dip_row.tank, 0.0), 3)
		doc.own_use_l = flt(dip_row.own_use_l, 3)
		doc.transfer_l = flt(dip_row.transfers_l, 3)
		doc.expected_l = flt(dip_row.expected_l, 3)
		doc.dip_l = flt(dip_row.dip_l, 3)
		doc.variance_l = flt(dip_row.variance_l, 3)
		doc.variance_pct = flt(dip_row.variance_pct, 4)
		doc.cashiers = cashiers_str
		doc.source = dip_row.source or "Manual"
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		posted.append(doc.name)
	return posted


def write_shift_nozzle_ledger(shift) -> list[str]:
	"""One Nozzle Ledger Entry per meter reading row (nozzle x segment)."""
	posting_date = str(get_datetime(shift.shift_end).date())
	posted: list[str] = []
	for row in shift.meter_readings:
		if not row.nozzle:
			continue
		doc = frappe.new_doc("Nozzle Ledger Entry")
		doc.company = shift.company
		doc.station = shift.station
		doc.posting_date = posting_date
		doc.forecourt_shift = shift.name
		doc.voucher_type = "Forecourt Shift"
		doc.voucher_no = shift.name
		doc.nozzle = row.nozzle
		doc.tank = row.tank
		doc.item = row.item
		doc.cashier = row.cashier
		doc.attendant = row.attendant
		doc.segment_no = row.segment_no
		doc.price = flt(row.price, 2)
		doc.source = row.source or "Manual"
		doc.shift_template = shift.shift_template
		doc.opening_elec_cash = flt(row.opening_elec_cash, 3)
		doc.closing_elec_cash = flt(row.closing_elec_cash, 3)
		doc.ecash_delta = flt(flt(row.closing_elec_cash, 3) - flt(row.opening_elec_cash, 3), 3)
		doc.opening_elec_meter = flt(row.opening_elec_meter, 3)
		doc.closing_elec_meter = flt(row.closing_elec_meter, 3)
		doc.evol_delta = flt(flt(row.closing_elec_meter, 3) - flt(row.opening_elec_meter, 3), 3)
		doc.opening_man_meter = flt(row.opening_man_meter, 3)
		doc.closing_man_meter = flt(row.closing_man_meter, 3)
		doc.mvol_delta = flt(flt(row.closing_man_meter, 3) - flt(row.opening_man_meter, 3), 3)
		doc.basis_meter = row.row_sales_basis or ""
		doc.gross_l = flt(row.basis_volume_l, 3)
		doc.test_l = flt(row.test_volume_l, 3)
		doc.own_use_l = flt(row.own_use_l, 3)
		doc.net_l = flt(row.net_volume_l, 3)
		doc.amount = flt(row.amount, 2)
		doc.drift_l = flt(row.drift_ecash_evol_l, 3)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		posted.append(doc.name)
	return posted


def write_shift_sales_ledger(shift) -> list[str]:
	"""Sales Ledger Entries: one per nozzle reading (Attributed) + credit sales + item sales (Exact)."""
	posting_date = str(get_datetime(shift.shift_end).date())
	posted: list[str] = []

	for row in shift.meter_readings:
		if not row.nozzle:
			continue
		doc = _base_sle(shift, posting_date)
		doc.cashier = row.cashier
		doc.item = row.item
		doc.is_fuel = 1
		doc.nozzle = row.nozzle
		doc.tank = row.tank
		doc.shift_template = shift.shift_template
		doc.qty = flt(row.net_volume_l, 3)
		doc.amount = flt(row.amount, 2)
		doc.basis = "Attributed"
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		posted.append(doc.name)

	for row in shift.credit_sales:
		if not row.item or not row.cashier:
			continue
		doc = _base_sle(shift, posting_date)
		doc.cashier = row.cashier
		doc.item = row.item
		doc.is_fuel = 1
		doc.nozzle = row.nozzle or ""
		doc.payment_type = "Credit"
		doc.customer = row.customer
		doc.customer_vehicle = row.vehicle
		doc.qty = flt(row.qty, 3)
		doc.amount = flt(row.amount, 2)
		doc.basis = "Exact"
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		posted.append(doc.name)

	for row in shift.item_sales:
		if not row.item or not row.cashier:
			continue
		is_fuel = frappe.db.get_value("Item", row.item, "fms_is_fuel") or 0
		doc = _base_sle(shift, posting_date)
		doc.cashier = row.cashier
		doc.item = row.item
		doc.is_fuel = is_fuel
		doc.qty = flt(row.qty, 3)
		doc.amount = flt(row.amount, 2)
		doc.basis = "Exact"
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		posted.append(doc.name)

	return posted


def write_shift_cashier_ledger(shift) -> list[str]:
	"""One Cashier Ledger Entry per cashier row."""
	posting_date = str(get_datetime(shift.shift_end).date())

	fuel_l_by_cashier: dict[str, float] = {}
	for row in shift.meter_readings:
		key = row.cashier
		if key:
			fuel_l_by_cashier[key] = flt(fuel_l_by_cashier.get(key, 0.0) + flt(row.net_volume_l, 3), 3)

	resolution_by_cashier: dict[str, tuple[str, float, str]] = {}
	for row in shift.resolutions:
		if row.resolution_for == "Cashier" and row.cashier:
			resolution_by_cashier[row.cashier] = (
				row.action or "",
				flt(row.amount, 2),
				getattr(row, "reason", "") or "",
			)

	posted: list[str] = []
	for cashier_row in shift.cashiers:
		if not cashier_row.cashier:
			continue
		resolution = resolution_by_cashier.get(cashier_row.cashier, ("", 0.0, ""))
		doc = frappe.new_doc("Cashier Ledger Entry")
		doc.company = shift.company
		doc.station = shift.station
		doc.posting_date = posting_date
		doc.forecourt_shift = shift.name
		doc.voucher_type = "Forecourt Shift"
		doc.voucher_no = shift.name
		doc.cashier = cashier_row.cashier
		doc.fuel_l = flt(fuel_l_by_cashier.get(cashier_row.cashier, 0.0), 3)
		doc.fuel_amount = flt(cashier_row.fuel_amount, 2)
		doc.item_amount = flt(cashier_row.item_amount, 2)
		doc.debt_receipts = flt(cashier_row.debt_receipts, 2)
		doc.float_amount = flt(cashier_row.float_amount, 2)
		doc.cash = flt(cashier_row.cash_counted, 2)
		doc.mobile = flt(cashier_row.mobile, 2)
		doc.card = flt(cashier_row.card, 2)
		doc.credit = flt(cashier_row.credit, 2)
		doc.voucher = flt(cashier_row.voucher, 2)
		doc.expenses = flt(cashier_row.expenses, 2)
		doc.drops = flt(cashier_row.drops, 2)
		doc.expected = flt(cashier_row.expected, 2)
		doc.accounted = flt(cashier_row.accounted, 2)
		doc.difference = flt(cashier_row.difference, 2)
		doc.resolution_action = resolution[0]
		doc.resolution_amount = resolution[1]
		doc.reason = resolution[2]
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		posted.append(doc.name)
	return posted


def update_nozzle_last_readings(shift) -> None:
	"""Update Nozzle.last_* to the closing readings of each nozzle's final segment."""
	last_by_nozzle: dict[str, object] = {}
	for row in shift.meter_readings:
		if not row.nozzle:
			continue
		prev = last_by_nozzle.get(row.nozzle)
		if prev is None or (row.segment_no or 0) > (prev.segment_no or 0):
			last_by_nozzle[row.nozzle] = row

	for nozzle_name, row in last_by_nozzle.items():
		updates: dict[str, object] = {"last_reading_shift": shift.name}
		if row.rec_elec_cash:
			updates["last_ecash"] = flt(row.closing_elec_cash, 3)
		if row.rec_elec_meter:
			updates["last_evol"] = flt(row.closing_elec_meter, 3)
		if row.rec_man_meter:
			updates["last_mvol"] = flt(row.closing_man_meter, 3)
		frappe.db.set_value("Nozzle", nozzle_name, updates)


# ── E03: GRN / Purchase Receipt delivery ──────────────────────────────────────


def write_delivery_wetstock_ledger(pr_doc) -> list[str]:
	"""One Wetstock Ledger Entry per delivery dip row (entry_type=Delivery)."""
	if not pr_doc.get("fms_delivery_dips"):
		return []
	posting_date = str(pr_doc.posting_date)
	station = getattr(pr_doc, "station", None)
	company = pr_doc.company
	posted: list[str] = []
	for row in pr_doc.fms_delivery_dips:
		if not row.tank:
			continue
		doc = frappe.new_doc("Wetstock Ledger Entry")
		doc.company = company
		doc.station = station
		doc.posting_date = posting_date
		doc.voucher_type = "Purchase Receipt"
		doc.voucher_no = pr_doc.name
		doc.entry_type = "Delivery"
		doc.tank = row.tank
		doc.item = row.item
		doc.receipt_l = flt(row.received_l, 3)
		doc.invoiced_l = flt(row.invoiced_l, 3)
		doc.delivery_variance_l = flt(row.variance_l, 3)
		doc.supplier = pr_doc.supplier
		doc.source = "Manual"
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		posted.append(doc.name)
	return posted


# ── E06: Tank Dip (spot dip) ──────────────────────────────────────────────────


def write_spot_dip_wetstock_ledger(dip_doc) -> str:
	"""One Wetstock Ledger Entry for a spot dip (entry_type=Spot Dip)."""
	station = getattr(dip_doc, "station", None)
	company = frappe.db.get_value("Station", station, "company") if station else None
	item = frappe.db.get_value("Fuel Tank", dip_doc.tank, "item") if dip_doc.tank else None
	posting_date = str(get_datetime(dip_doc.dipped_at).date()) if dip_doc.dipped_at else today()
	doc = frappe.new_doc("Wetstock Ledger Entry")
	doc.company = company
	doc.station = station
	doc.posting_date = posting_date
	doc.voucher_type = "Tank Dip"
	doc.voucher_no = dip_doc.name
	doc.entry_type = "Spot Dip"
	doc.tank = dip_doc.tank
	doc.item = item
	doc.dip_l = flt(flt(dip_doc.volume_l, 3) - flt(dip_doc.water_l, 3), 3)
	doc.dip_entry_mode = dip_doc.dip_entry_mode or "Litres"
	doc.source = "Manual"
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


# ── E08: Meter Change ─────────────────────────────────────────────────────────


def write_meter_change_nozzle_ledger(mc_doc) -> str:
	"""One Nozzle Ledger Entry recording meter state at point of change."""
	station = getattr(mc_doc, "station", None)
	company = frappe.db.get_value("Station", station, "company") if station else None
	nozzle_data = frappe.db.get_value("Nozzle", mc_doc.nozzle, ["tank", "item"], as_dict=True) or {}
	posting_date = str(get_datetime(mc_doc.changed_at).date()) if mc_doc.changed_at else today()
	doc = frappe.new_doc("Nozzle Ledger Entry")
	doc.company = company
	doc.station = station
	doc.posting_date = posting_date
	doc.voucher_type = "Meter Change"
	doc.voucher_no = mc_doc.name
	doc.nozzle = mc_doc.nozzle
	doc.tank = nozzle_data.get("tank")
	doc.item = nozzle_data.get("item")
	doc.opening_elec_cash = flt(mc_doc.old_final_ecash, 3)
	doc.closing_elec_cash = flt(mc_doc.new_start_ecash, 3)
	doc.ecash_delta = flt(flt(mc_doc.new_start_ecash) - flt(mc_doc.old_final_ecash), 3)
	doc.opening_elec_meter = flt(mc_doc.old_final_evol, 3)
	doc.closing_elec_meter = flt(mc_doc.new_start_evol, 3)
	doc.evol_delta = flt(flt(mc_doc.new_start_evol) - flt(mc_doc.old_final_evol), 3)
	doc.opening_man_meter = flt(mc_doc.old_final_mvol, 3)
	doc.closing_man_meter = flt(mc_doc.new_start_mvol, 3)
	doc.mvol_delta = flt(flt(mc_doc.new_start_mvol) - flt(mc_doc.old_final_mvol), 3)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


# ── private helpers ───────────────────────────────────────────────────────────


def _base_sle(shift, posting_date: str):
	doc = frappe.new_doc("Sales Ledger Entry")
	doc.company = shift.company
	doc.station = shift.station
	doc.posting_date = posting_date
	doc.forecourt_shift = shift.name
	doc.voucher_type = "Forecourt Shift"
	doc.voucher_no = shift.name
	return doc
