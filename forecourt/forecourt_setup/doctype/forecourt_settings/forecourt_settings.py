import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M603, FMSValidationError


class ForecourtSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		accountable_person_label: DF.Literal["Cashier", "Salesperson"]
		allow_backdated_shift_days: DF.Int
		allow_estimated_segments: DF.Check
		background_close_threshold: DF.Int
		dip_entry_mode: DF.Literal["Depth via calibration chart", "Litres entered directly"]
		drift_requires_reason: DF.Check
		drift_tolerance_l: DF.Float
		drift_tolerance_pct: DF.Percent
		price_change_mode: DF.Literal["Latest price with segments", "Between shifts only"]
		record_elec_cash: DF.Check
		record_elec_meter: DF.Check
		record_man_meter: DF.Check
		require_expense_receipt: DF.Check
		require_meter_reading_photo: DF.Check
		sales_basis: DF.Literal["Elec Cash", "Elec Meter", "Man Meter", "Highest"]

	# end: auto-generated types

	def validate(self) -> None:
		self._validate_meters()

	def _validate_meters(self) -> None:
		if not (self.record_elec_cash or self.record_elec_meter or self.record_man_meter):
			raise FMSValidationError(
				FMS_M603,
				_("At least one meter (Elec Cash, Elec Meter or Man Meter) must be recorded."),
			)

		basis_requires: dict[str, tuple[bool, str]] = {
			"Elec Cash": (bool(self.record_elec_cash), _("Record Elec Cash")),
			"Elec Meter": (bool(self.record_elec_meter), _("Record Elec Meter")),
			"Man Meter": (bool(self.record_man_meter), _("Record Man Meter")),
		}

		if self.sales_basis in basis_requires:
			recorded, label = basis_requires[self.sales_basis]
			if not recorded:
				raise FMSValidationError(
					FMS_M603,
					_(
						"Sales basis {0} is not one of the recorded meters. "
						"Enable {1} or choose another basis."
					).format(self.sales_basis, label),
				)
		elif self.sales_basis == "Highest":
			if not (self.record_elec_cash and self.record_elec_meter):
				raise FMSValidationError(
					FMS_M603,
					_(
						"Sales basis Highest compares Elec Cash and Elec Meter. "
						"Both Record Elec Cash and Record Elec Meter must be enabled."
					),
				)
