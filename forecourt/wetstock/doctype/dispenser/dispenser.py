from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M603, FMSValidationError

_BASIS_TO_METER: dict[str, str] = {
	"Elec Cash": "record_elec_cash",
	"Elec Meter": "record_elec_meter",
	"Man Meter": "record_man_meter",
}


class Dispenser(Document):
	def validate(self) -> None:
		if self.meters_override:
			self._validate_meters()

	def _validate_meters(self) -> None:
		recorded = any([self.record_elec_cash, self.record_elec_meter, self.record_man_meter])
		if not recorded:
			raise FMSValidationError(
				FMS_M603,
				_("[{0}] At least one meter must be recorded when overriding.").format(FMS_M603),
			)
		if self.sales_basis and self.sales_basis != "Highest":
			meter_field = _BASIS_TO_METER.get(self.sales_basis)
			if meter_field and not getattr(self, meter_field):
				raise FMSValidationError(
					FMS_M603,
					_("[{0}] Sales basis {1} requires its meter to be recorded.").format(
						FMS_M603, self.sales_basis
					),
				)
