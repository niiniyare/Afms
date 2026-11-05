"""Cancel guards for native documents linked to a Forecourt Shift (FMS-C502)."""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.errors import FMS_C502, FMSValidationError


def on_cancel_native(doc, method=None) -> None:
	"""Block cancellation of any native document linked to a Closed shift."""
	shift = getattr(doc, "fms_forecourt_shift", None)
	if not shift:
		return
	if frappe.flags.fms_correction:
		return
	status = frappe.db.get_value("Forecourt Shift", shift, "status")
	if status == "Closed":
		raise FMSValidationError(
			FMS_C502,
			_(
				"[FMS-C502] {0} {1} is linked to a Closed Forecourt Shift ({2}) and cannot be "
				"cancelled directly. Use Shift Correction."
			).format(doc.doctype, doc.name, shift),
		)
