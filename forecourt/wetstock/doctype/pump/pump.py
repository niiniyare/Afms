from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M603, FMSValidationError

_BASIS_TO_METER: dict[str, str] = {
	"Elec Cash": "record_elec_cash",
	"Elec Mtr": "record_elec_meter",
	"Man Mtr": "record_man_meter",
}


class Pump(Document):
	def validate(self) -> None:
		if self.meters_override:
			self._validate_meters()

	def _validate_meters(self) -> None:
		sales_basis = self.sales_basis
		if not sales_basis:
			return
		if sales_basis == "Highest":
			recorded = sum(
				[
					int(bool(self.record_elec_cash)),
					int(bool(self.record_elec_meter)),
					int(bool(self.record_man_meter)),
				]
			)
			if recorded < 2:
				raise FMSValidationError(
					FMS_M603,
					_("[{0}] Sales basis Highest requires at least two meters to be recorded.").format(
						FMS_M603
					),
				)
		else:
			required_field = _BASIS_TO_METER.get(sales_basis)
			if required_field and not self.get(required_field):
				raise FMSValidationError(
					FMS_M603,
					_("[{0}] Sales basis {1} requires the corresponding meter to be recorded.").format(
						FMS_M603, frappe.bold(sales_basis)
					),
				)
