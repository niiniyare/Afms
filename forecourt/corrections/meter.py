"""
Shift Correction applier: Meter reading (FMS-G03).

Corrects a closing meter reading:
- Supersedes the affected Nozzle and Sales Ledger rows for the corrected nozzle.
- Issues a credit note against the walk-in invoice for the sales amount reduction
  (no stock movement; the dips already reflect the fuel as dispensed).
- Updates the next shift's opening reading if it is still open.
- New cashier balance differences go to resolutions on the correction.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_datetime

from forecourt.calc import meters as calc_meters
from forecourt.errors import FMS_C504, FMSValidationError
from forecourt.posting.sales import post_walkin_credit_note


def apply(correction) -> None:
	applied: list[str] = []

	for item in correction.items:
		if item.target_type != "Meter Reading":
			frappe.throw(
				_(
					"Meter reading correction expects items with target_type 'Meter Reading', got '{0}'."
				).format(item.target_type)
			)
		if not item.target_row or not item.field:
			frappe.throw(
				_("Correction item row {0} requires target_row (child row name) and field.").format(item.idx)
			)

		shift = frappe.get_doc("Forecourt Shift", correction.forecourt_shift)
		posting_date = str(get_datetime(shift.shift_end).date())

		target_reading = next((row for row in shift.meter_readings if row.name == item.target_row), None)

		if target_reading:
			old_amount = flt(target_reading.amount, 2)
			setattr(target_reading, item.field, flt(item.new_value, 3))
			net_l, new_amount = _recomputed_sales(target_reading)
			target_reading.net_volume_l = net_l
			target_reading.amount = new_amount

			# Reject unsupported corrections before any ledger row is touched,
			# so a refused correction cannot depend on transaction rollback.
			delta = flt(old_amount - new_amount, 2)
			if delta < 0:
				raise FMSValidationError(
					FMS_C504,
					_(
						"Correction raises the sale of nozzle {0} by {1}. Raising a walk-in sale is not supported yet."
					).format(target_reading.nozzle, flt(-delta, 2)),
				)

			# 1. Supersede only the Nozzle and Sales Ledger rows of the corrected nozzle
			for nle_name in _active_rows(
				"Nozzle Ledger Entry", correction.forecourt_shift, target_reading.nozzle
			):
				frappe.get_doc("Nozzle Ledger Entry", nle_name).db_set(
					"superseded_by", correction.name, update_modified=False
				)
				applied.append(f"Superseded Nozzle Ledger Entry: {nle_name}")
			for sle_name in _active_rows(
				"Sales Ledger Entry", correction.forecourt_shift, target_reading.nozzle, basis="Attributed"
			):
				frappe.get_doc("Sales Ledger Entry", sle_name).db_set(
					"superseded_by", correction.name, update_modified=False
				)
				applied.append(f"Superseded Sales Ledger Entry: {sle_name}")

			# 2. Write corrected Nozzle and Sales Ledger Entries
			new_nle = frappe.new_doc("Nozzle Ledger Entry")
			new_nle.company = shift.company
			new_nle.station = shift.station
			new_nle.posting_date = posting_date
			new_nle.forecourt_shift = shift.name
			new_nle.voucher_type = "Forecourt Shift"
			new_nle.voucher_no = shift.name
			new_nle.nozzle = target_reading.nozzle
			new_nle.tank = target_reading.tank
			new_nle.item = target_reading.item
			new_nle.cashier = target_reading.cashier
			new_nle.segment_no = target_reading.segment_no
			new_nle.price = flt(target_reading.price, 2)
			new_nle.correction = correction.name
			new_nle.opening_elec_cash = flt(target_reading.opening_elec_cash, 3)
			new_nle.closing_elec_cash = flt(target_reading.closing_elec_cash, 3)
			new_nle.net_volume_l = net_l
			new_nle.amount = new_amount
			new_nle.flags.ignore_permissions = True
			new_nle.insert(ignore_permissions=True)
			applied.append(f"New Nozzle Ledger Entry: {new_nle.name}")

			new_sle = frappe.new_doc("Sales Ledger Entry")
			new_sle.company = shift.company
			new_sle.station = shift.station
			new_sle.posting_date = posting_date
			new_sle.forecourt_shift = shift.name
			new_sle.voucher_type = "Forecourt Shift"
			new_sle.voucher_no = shift.name
			new_sle.cashier = target_reading.cashier
			new_sle.item = target_reading.item
			new_sle.is_fuel = 1
			new_sle.nozzle = target_reading.nozzle
			new_sle.tank = target_reading.tank
			new_sle.shift_template = shift.shift_template
			new_sle.qty = net_l
			new_sle.amount = new_amount
			new_sle.basis = "Attributed"
			new_sle.correction = correction.name
			new_sle.flags.ignore_permissions = True
			new_sle.insert(ignore_permissions=True)
			applied.append(f"New Sales Ledger Entry: {new_sle.name}")

			# 3. Credit note against the walk-in invoice for the sales reduction
			if delta > 0:
				price = flt(target_reading.price, 2)
				warehouse = frappe.db.get_value("Fuel Tank", target_reading.tank, "warehouse")
				credit_note = post_walkin_credit_note(
					shift, target_reading.item, flt(delta / price, 3), price, warehouse
				)
				applied.append(f"Walk-in credit note: {credit_note}")

		# 4. Update next shift opening if still open
		if correction.next_shift:
			next_shift = frappe.get_doc("Forecourt Shift", correction.next_shift)
			if next_shift.docstatus == 0:
				for row in next_shift.meter_readings:
					if row.nozzle == (target_reading.nozzle if target_reading else None):
						row.opening_elec_cash = flt(item.new_value, 3)
						row.db_set("opening_elec_cash", flt(item.new_value, 3), update_modified=False)
						applied.append(f"Updated next shift opening: {correction.next_shift}")
						break

	correction.db_set(
		"applied_documents",
		"\n".join(applied) if applied else "",
		update_modified=False,
	)


def _active_rows(doctype: str, shift: str, nozzle: str, basis: str | None = None) -> list[str]:
	filters: dict = {
		"forecourt_shift": shift,
		"nozzle": nozzle,
		"is_cancelled": 0,
		"superseded_by": ["is", "not set"],
	}
	if basis:
		filters["basis"] = basis
	return frappe.get_all(doctype, filters=filters, pluck="name")


def _recomputed_sales(row) -> tuple[float, float]:
	"""Net litres and amount for an E-cash based meter row, as the shift controller computes them."""
	price = flt(row.price, 2)
	ecash = calc_meters.MeterReading(
		opening=flt(row.opening_elec_cash),
		closing=flt(row.closing_elec_cash),
		rollover=bool(row.rollover_elec_cash),
		rollover_max=flt(frappe.db.get_value("Nozzle", row.nozzle, "ecash_max") or 0),
	)
	result = calc_meters.segment_sales(
		ecash=ecash, evol=None, mvol=None, price=price, sales_basis="Elec Cash"
	)
	net_l = flt(result.basis_litres - flt(row.test_volume_l) - flt(row.own_use_l), 3)
	return net_l, flt(net_l * price, 2)
