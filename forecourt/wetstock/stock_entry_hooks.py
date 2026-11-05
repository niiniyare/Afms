"""doc_events handlers for Stock Entry (Fuel Own Use validation, E05; shift default, F06)."""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.errors import FMS_C502, FMSValidationError

_FUEL_OWN_USE_TYPE = "Fuel Own Use"


def validate_stock_entry(doc, method=None) -> None:
	"""Validate Fuel Own Use entries; default shift to open shift at the station (F06)."""
	if doc.stock_entry_type != _FUEL_OWN_USE_TYPE:
		return

	# F06: default fms_forecourt_shift to the open shift at the station
	if not doc.get("fms_forecourt_shift") and doc.get("station"):
		open_shift = frappe.db.get_value(
			"Forecourt Shift",
			{"station": doc.station, "docstatus": 0},
			"name",
			order_by="shift_start desc",
		)
		if open_shift:
			doc.fms_forecourt_shift = open_shift

	if not doc.remarks:
		frappe.throw(
			_("[FMS-E05] Fuel Own Use requires a narration (remarks) explaining the use."),
			frappe.ValidationError,
		)

	if not doc.get("fms_use_purpose"):
		frappe.throw(
			_("[FMS-E05] Fuel Own Use requires an Own Use Purpose."),
			frappe.ValidationError,
		)

	if not doc.get("fms_nozzle"):
		frappe.throw(
			_("[FMS-E05] Fuel Own Use requires a Nozzle."),
			frappe.ValidationError,
		)

	purpose_doc = frappe.get_cached_doc("Own Use Purpose", doc.fms_use_purpose)
	if purpose_doc.requires_vehicle and not doc.get("fms_vehicle_or_asset"):
		frappe.throw(
			_("[FMS-E05] Own Use Purpose '{0}' requires a Vehicle / Asset reference.").format(
				doc.fms_use_purpose
			),
			frappe.ValidationError,
		)

	company = doc.company
	if company and doc.items:
		account = None
		for acc_row in purpose_doc.get("accounts", []):
			if acc_row.company == company:
				account = acc_row.expense_account
				break
		if account:
			for item in doc.items:
				if not item.expense_account:
					item.expense_account = account


def on_cancel_stock_entry(doc, method=None) -> None:
	"""Block cancellation if a closed shift used this entry."""
	if not doc.get("fms_forecourt_shift"):
		return
	shift_status = frappe.db.get_value("Forecourt Shift", doc.fms_forecourt_shift, "status")
	if shift_status == "Closed" and not frappe.flags.fms_correction:
		raise FMSValidationError(
			FMS_C502,
			_(
				"[FMS-C502] Stock Entry {0} is linked to a Closed shift and cannot be "
				"cancelled directly. Use Shift Correction."
			).format(doc.name),
		)
