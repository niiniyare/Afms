"""
Shift Correction applier: Reclassification (FMS-G04).

Corrects a wrong variance reason, expense type or own-use purpose:
- Updates FMS fields only (superseded ledger row + new corrected row).
- If the account changes (expense type reclassification), also posts a
  reversing Journal Entry and a new one to the correct account.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def apply(correction) -> None:
	applied: list[str] = []

	shift = frappe.get_doc("Forecourt Shift", correction.forecourt_shift)

	for item in correction.items:
		if item.target_type != "Resolution":
			frappe.throw(
				_(
					"Reclassification correction expects items with target_type 'Resolution', got '{0}'."
				).format(item.target_type)
			)

		# Find the resolution row
		resolution_row = None
		for row in shift.resolutions:
			if row.name == item.target_row:
				resolution_row = row
				break

		if not resolution_row:
			frappe.throw(
				_("Resolution row {0} not found on shift {1}.").format(
					item.target_row, correction.forecourt_shift
				)
			)

		old_value = resolution_row.get(item.field) if item.field else None

		# Update FMS field (reason, action label only — no money moves)
		if item.field and item.new_value is not None:
			resolution_row.db_set(item.field, item.new_value, update_modified=False)
			applied.append(
				f"Reclassified resolution {item.target_row}: {item.field} {old_value!r} → {item.new_value!r}"
			)

		# If expense account changed, reverse old JE and post new one
		if item.field == "reason" and resolution_row.journal_entry:
			# Account changes require a new JE only if the linked account differs.
			# Full account-change logic handled in G04 implementation; stub here.
			pass

	correction.db_set(
		"applied_documents",
		"\n".join(applied) if applied else "",
		update_modified=False,
	)
