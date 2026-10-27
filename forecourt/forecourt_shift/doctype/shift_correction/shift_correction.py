"""Shift Correction controller — catalogue 10.5, design guide 6.8."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_C501, FMSValidationError


class ShiftCorrection(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from forecourt.forecourt_shift.doctype.shift_correction_item.shift_correction_item import (
			ShiftCorrectionItem,
		)
		from forecourt.forecourt_shift.doctype.shift_resolution.shift_resolution import (
			ShiftResolution,
		)

		applied_documents: DF.SmallText | None
		approved_by: DF.Link | None
		company: DF.Link | None
		correction_type: DF.Literal[
			"Native document",
			"Meter reading",
			"Dip",
			"Cashier count",
			"Reclassification",
			"Whole-shift cancellation",
		]
		evidence: DF.Attach | None
		forecourt_shift: DF.Link
		items: DF.Table[ShiftCorrectionItem]
		next_shift: DF.Link | None
		reason: DF.SmallText
		resolutions: DF.Table[ShiftResolution]
		station: DF.Link | None

	# end: auto-generated types

	def validate(self) -> None:
		self._validate_shift_is_closed()
		self._validate_items_not_empty()

	def before_submit(self) -> None:
		if frappe.session.user == frappe.db.get_value("Forecourt Shift", self.forecourt_shift, "owner"):
			raise FMSValidationError(
				FMS_C501,
				_("[FMS-C501] The approver cannot be the user who prepared shift {0}.").format(
					self.forecourt_shift
				),
			)
		self.approved_by = frappe.session.user

	def on_submit(self) -> None:
		"""Apply the correction in one transaction."""
		frappe.flags.fms_correction = True
		try:
			self._apply()
		finally:
			frappe.flags.fms_correction = False
		frappe.db.set_value("Forecourt Shift", self.forecourt_shift, "status", "Corrected")

	def on_cancel(self) -> None:
		frappe.throw(_("Shift Corrections cannot be cancelled. Fix mistakes with a further correction."))

	# ── private ──────────────────────────────────────────────────────────────

	def _validate_shift_is_closed(self) -> None:
		status = frappe.db.get_value("Forecourt Shift", self.forecourt_shift, "status")
		if status not in ("Closed", "Corrected"):
			frappe.throw(
				_(
					"Shift {0} must be Closed before a correction can be created (current status: {1})."
				).format(self.forecourt_shift, status)
			)

	def _validate_items_not_empty(self) -> None:
		if not self.items:
			frappe.throw(_("At least one correction item is required."))

	def _apply(self) -> None:
		"""Dispatch to the appropriate correction module based on correction_type."""
		ctype = self.correction_type
		if ctype == "Native document":
			from forecourt.corrections.native import apply as apply_native

			apply_native(self)
		elif ctype == "Meter reading":
			from forecourt.corrections.meter import apply as apply_meter

			apply_meter(self)
		elif ctype == "Dip":
			from forecourt.corrections.dip import apply as apply_dip

			apply_dip(self)
		elif ctype == "Cashier count":
			from forecourt.corrections.cashier import apply as apply_cashier

			apply_cashier(self)
		elif ctype == "Reclassification":
			from forecourt.corrections.reclassify import apply as apply_reclassify

			apply_reclassify(self)
		elif ctype == "Whole-shift cancellation":
			from forecourt.corrections.whole_shift import apply as apply_whole_shift

			apply_whole_shift(self)
		else:
			frappe.throw(_("Unknown correction type: {0}").format(ctype))
