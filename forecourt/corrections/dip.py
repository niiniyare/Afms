"""
Shift Correction applier: Tank Dip (FMS-G04).

Corrects a closing dip reading:
- Supersedes the affected Wetstock Ledger row.
- Posts a new back-dated Stock Reconciliation at the corrected volume.
- Supersedes and re-bases the next shift's Wetstock Ledger opening row.
- Updates the next shift's opening dip if it is still open (D22, proposed).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_datetime


def apply(correction) -> None:
	applied: list[str] = []

	for item in correction.items:
		if item.target_type != "Tank Dip":
			frappe.throw(
				_("Dip correction expects items with target_type 'Tank Dip', got '{0}'.").format(
					item.target_type
				)
			)
		if not item.target_row:
			frappe.throw(_("Correction item row {0} requires target_row.").format(item.idx))

		shift = frappe.get_doc("Forecourt Shift", correction.forecourt_shift)

		# Find the dip row
		target_dip = None
		for row in shift.tank_dips:
			if row.name == item.target_row:
				target_dip = row
				break

		if not target_dip:
			frappe.throw(
				_("Tank dip row {0} not found on shift {1}.").format(
					item.target_row, correction.forecourt_shift
				)
			)

		# 1. Supersede the Wetstock Ledger row for this shift + tank
		wle_names = frappe.get_all(
			"Wetstock Ledger Entry",
			filters={
				"forecourt_shift": correction.forecourt_shift,
				"tank": target_dip.tank,
				"entry_type": "Shift",
				"is_cancelled": 0,
				"superseded_by": ["is", "not set"],
			},
			pluck="name",
		)
		for wle_name in wle_names:
			frappe.db.set_value(
				"Wetstock Ledger Entry", wle_name, "superseded_by", correction.name, update_modified=False
			)
			applied.append(f"Superseded Wetstock Ledger Entry: {wle_name}")

		# 2. Write corrected Wetstock Ledger Entry
		posting_date = str(get_datetime(shift.shift_end).date())
		new_dip_l = flt(item.new_value, 3)
		expected_l = flt(target_dip.expected_l, 3)

		new_wle = frappe.new_doc("Wetstock Ledger Entry")
		new_wle.company = shift.company
		new_wle.station = shift.station
		new_wle.posting_date = posting_date
		new_wle.forecourt_shift = shift.name
		new_wle.voucher_type = "Shift Correction"
		new_wle.voucher_no = correction.name
		new_wle.entry_type = "Shift"
		new_wle.tank = target_dip.tank
		new_wle.item = target_dip.item
		new_wle.shift_start = shift.shift_start
		new_wle.shift_end = shift.shift_end
		new_wle.opening_l = flt(target_dip.opening_l, 3)
		new_wle.receipt_l = flt(target_dip.receipts_l, 3)
		new_wle.sales_l = flt(target_dip.sales_l, 3)
		new_wle.own_use_l = flt(target_dip.own_use_l, 3)
		new_wle.expected_l = expected_l
		new_wle.dip_l = new_dip_l
		new_wle.variance_l = flt(new_dip_l - expected_l, 3)
		new_wle.variance_pct = flt((new_dip_l - expected_l) / expected_l * 100 if expected_l else 0.0, 4)
		new_wle.correction = correction.name
		new_wle.flags.ignore_permissions = True
		new_wle.insert(ignore_permissions=True)
		applied.append(f"New Wetstock Ledger Entry: {new_wle.name}")

		# 3. Post a back-dated Stock Reconciliation at the corrected dip volume
		stock_rec = frappe.new_doc("Stock Reconciliation")
		stock_rec.company = shift.company
		stock_rec.posting_date = posting_date
		stock_rec.posting_time = str(get_datetime(shift.shift_end).time())
		stock_rec.purpose = "Stock Reconciliation"
		stock_rec.fms_forecourt_shift = correction.forecourt_shift
		stock_rec.remarks = f"Dip correction {correction.name} for shift {correction.forecourt_shift}"

		warehouse = frappe.db.get_value("Fuel Tank", target_dip.tank, "warehouse")
		if warehouse:
			stock_rec.append(
				"items",
				{
					"item_code": target_dip.item,
					"warehouse": warehouse,
					"qty": new_dip_l,
				},
			)
			stock_rec.flags.ignore_permissions = True
			stock_rec.insert(ignore_permissions=True)
			stock_rec.submit()
			applied.append(f"Stock Reconciliation: {stock_rec.name}")

		# 4. Update next shift opening if still open (D22, proposed)
		if correction.next_shift:
			next_shift = frappe.get_doc("Forecourt Shift", correction.next_shift)
			if next_shift.docstatus == 0:
				for row in next_shift.tank_dips:
					if row.tank == target_dip.tank:
						row.db_set("opening_l", new_dip_l, update_modified=False)
						applied.append(f"Updated next shift opening dip: {correction.next_shift}")
						break

	correction.db_set(
		"applied_documents",
		"\n".join(applied) if applied else "",
		update_modified=False,
	)
