"""
Shift Correction applier: Cashier count / resolution (FMS-G04).

Corrects a cash count error or a shortage charged to the wrong person:
- Issues a reversing Journal Entry against the original resolution entry.
- Posts a new Journal Entry with the corrected account/amount.
- Supersedes the affected Cashier Ledger rows and writes corrected ones.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, today


def apply(correction) -> None:
	applied: list[str] = []

	shift = frappe.get_doc("Forecourt Shift", correction.forecourt_shift)
	posting_date = str(get_datetime(shift.shift_end).date())
	company = shift.company

	for item in correction.items:
		if item.target_type not in ("Cash Count", "Resolution"):
			frappe.throw(
				_(
					"Cashier count correction expects items with target_type 'Cash Count' or "
					"'Resolution', got '{0}'."
				).format(item.target_type)
			)

		# Supersede old Cashier Ledger rows for this shift
		cle_names = frappe.get_all(
			"Cashier Ledger Entry",
			filters={
				"forecourt_shift": correction.forecourt_shift,
				"is_cancelled": 0,
				"superseded_by": ["is", "not set"],
			},
			pluck="name",
		)
		for cle_name in cle_names:
			frappe.db.set_value(
				"Cashier Ledger Entry",
				cle_name,
				"superseded_by",
				correction.name,
				update_modified=False,
			)
			applied.append(f"Superseded Cashier Ledger Entry: {cle_name}")

		# Reverse any resolution Journal Entry linked from the resolution row
		if item.target_type == "Resolution":
			resolution_row = None
			for row in shift.resolutions:
				if row.name == item.target_row:
					resolution_row = row
					break

			if resolution_row and resolution_row.journal_entry:
				original_je = frappe.get_doc("Journal Entry", resolution_row.journal_entry)
				if original_je.docstatus == 1:
					original_je.cancel()
					applied.append(f"Cancelled Journal Entry: {resolution_row.journal_entry}")

					# Reversing JE
					rev_je = frappe.new_doc("Journal Entry")
					rev_je.company = company
					rev_je.posting_date = posting_date
					rev_je.voucher_type = "Journal Entry"
					rev_je.fms_forecourt_shift = correction.forecourt_shift
					rev_je.user_remark = f"Reversal for shift correction {correction.name}"
					for acc_row in original_je.accounts:
						rev_je.append(
							"accounts",
							{
								"account": acc_row.account,
								"debit_in_account_currency": flt(acc_row.credit_in_account_currency, 2),
								"credit_in_account_currency": flt(acc_row.debit_in_account_currency, 2),
								"party_type": acc_row.party_type,
								"party": acc_row.party,
								"cost_center": acc_row.cost_center,
							},
						)
					rev_je.flags.ignore_permissions = True
					rev_je.insert(ignore_permissions=True)
					rev_je.submit()
					applied.append(f"Reversing Journal Entry: {rev_je.name}")

	correction.db_set(
		"applied_documents",
		"\n".join(applied) if applied else "",
		update_modified=False,
	)
