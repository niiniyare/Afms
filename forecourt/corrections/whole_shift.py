"""
Shift Correction applier: Whole-shift cancellation (FMS-G05).

Only for the latest closed shift at the station. Requires System Manager
role plus director approval. Cancels all generated documents in reverse
order: Stock Reconciliation → Journal Entry → Payment Entry → Sales Invoice.
Shifts in a closed accounting period cannot be cancelled (FMS-C503).
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.errors import FMS_C503, FMSValidationError

_CANCEL_ORDER = [
	"Stock Reconciliation",
	"Stock Entry",
	"Journal Entry",
	"Payment Entry",
	"Delivery Note",
	"Sales Invoice",
]


def apply(correction) -> None:
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Whole-shift cancellation requires the System Manager role."))

	shift_name = correction.forecourt_shift
	shift = frappe.get_doc("Forecourt Shift", shift_name)

	_assert_latest_shift(shift)
	_assert_period_open(shift)

	applied: list[str] = []

	for doctype in _CANCEL_ORDER:
		docs = frappe.get_all(
			doctype,
			filters={"fms_forecourt_shift": shift_name, "docstatus": 1},
			pluck="name",
		)
		for name in docs:
			doc = frappe.get_doc(doctype, name)
			doc.cancel()
			applied.append(f"Cancelled: {doctype} {name}")

	# Mark the shift as cancelled
	frappe.db.set_value("Forecourt Shift", shift_name, "docstatus", 2)
	frappe.db.set_value("Forecourt Shift", shift_name, "status", "Cancelled")

	correction.db_set(
		"applied_documents",
		"\n".join(applied) if applied else "",
		update_modified=False,
	)


def _assert_latest_shift(shift) -> None:
	later = frappe.db.count(
		"Forecourt Shift",
		{
			"station": shift.station,
			"docstatus": 1,
			"shift_start": [">", shift.shift_start],
		},
	)
	if later:
		raise FMSValidationError(
			FMS_C503,
			_(
				"[FMS-C503] Whole-shift cancellation is only allowed on the latest closed shift "
				"at station {0}. There are {1} later shift(s)."
			).format(shift.station, later),
		)


def _assert_period_open(shift) -> None:
	from frappe.utils import get_datetime

	posting_date = str(get_datetime(shift.shift_end).date())
	closed = frappe.db.get_value(
		"Fiscal Year",
		{"year_start_date": ["<=", posting_date], "year_end_date": [">=", posting_date]},
		"is_fiscal_year_closed",
	)
	if closed:
		frappe.throw(_("Shift {0} falls in a closed fiscal year and cannot be cancelled.").format(shift.name))
