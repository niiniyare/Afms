import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M606, FMS_M607, FMSValidationError

_LAST_FIELDS: frozenset[str] = frozenset(["last_ecash", "last_evol", "last_mvol"])


class Nozzle(Document):
	def validate(self) -> None:
		self._validate_tank_station()
		self._validate_last_fields()

	def _validate_tank_station(self) -> None:
		if not self.tank:
			return
		tank_station = frappe.db.get_value("Fuel Tank", self.tank, "station")
		if tank_station and tank_station != self.station:
			raise FMSValidationError(
				FMS_M606,
				_("[{0}] Tank {1} belongs to station {2}, not {3}.").format(
					FMS_M606, self.tank, tank_station, self.station
				),
			)

	def _validate_last_fields(self) -> None:
		if self.flags.get("from_fms"):
			return
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		for field in _LAST_FIELDS:
			if getattr(self, field) != getattr(before, field):
				raise FMSValidationError(
					FMS_M607,
					_("[{0}] Last readings can only be updated by a shift close or Meter Change.").format(
						FMS_M607
					),
				)
