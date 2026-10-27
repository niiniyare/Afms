"""F16: Background close for large Forecourt Shifts."""

from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist()
def close_shift(shift_name: str) -> str:
	"""Close a shift directly (< threshold) or enqueue a background job (>= threshold).

	Returns "submitted" or "enqueued".
	"""
	frappe.has_permission("Forecourt Shift", "submit", shift_name, throw=True)

	shift = frappe.get_doc("Forecourt Shift", shift_name)
	if shift.docstatus != 0:
		frappe.throw(_("[FMS-F16] Shift {0} is already submitted.").format(shift_name))
	if shift.status == "Closing":
		frappe.throw(_("[FMS-F16] Shift {0} is already being closed.").format(shift_name))

	threshold = int(frappe.db.get_single_value("Forecourt Settings", "background_close_threshold") or 200)
	if len(shift.collections) < threshold:
		shift.submit()
		return "submitted"

	frappe.db.set_value("Forecourt Shift", shift_name, "status", "Closing", update_modified=False)
	frappe.enqueue(
		"forecourt.forecourt_shift.close.close_shift_in_background",
		queue="long",
		job_id=f"close_shift_{shift_name}",
		enqueue_after_commit=True,
		shift_name=shift_name,
	)
	return "enqueued"


def close_shift_in_background(shift_name: str) -> None:
	"""Background job: submit the shift, reset to Reconciled with error on failure."""
	try:
		frappe.flags.fms_background_close = True
		shift = frappe.get_doc("Forecourt Shift", shift_name)
		shift.submit()
		frappe.publish_realtime(
			"shift_closed",
			{"shift": shift_name, "status": "Closed"},
			doctype="Forecourt Shift",
			docname=shift_name,
		)
	except Exception:
		frappe.db.rollback()
		tb = frappe.get_traceback()
		frappe.log_error(tb, f"Close shift failed: {shift_name}")
		frappe.db.set_value(
			"Forecourt Shift",
			shift_name,
			"status",
			"Reconciled",
			update_modified=False,
		)
		try:
			frappe.get_doc("Forecourt Shift", shift_name).add_comment(
				"Comment",
				_("Background close failed. Error:\n{0}").format(tb[:500]),
			)
		except Exception:
			pass
		frappe.db.commit()
		frappe.publish_realtime(
			"shift_closed",
			{"shift": shift_name, "status": "Reconciled", "error": True},
			doctype="Forecourt Shift",
			docname=shift_name,
		)
	finally:
		frappe.flags.fms_background_close = False
