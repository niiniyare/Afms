import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.calc.calibration import validate_rows
from forecourt.errors import FMS_M605, FMSValidationError


class TankCalibrationChart(Document):
	def validate(self) -> None:
		self._validate_rows()
		self._compute_maxima()
		self._warn_capacity_mismatch()

	def _validate_rows(self) -> None:
		pairs = [(r.depth_mm, r.volume_l) for r in (self.rows or [])]
		errors = validate_rows(pairs)
		if errors:
			raise FMSValidationError(
				FMS_M605,
				_("[{0}] Calibration chart rows are not strictly increasing: {1}").format(
					FMS_M605, "; ".join(errors)
				),
			)
		if self.water_rows:
			water_pairs = [(r.depth_mm, r.volume_l) for r in self.water_rows]
			water_errors = validate_rows(water_pairs)
			if water_errors:
				raise FMSValidationError(
					FMS_M605,
					_("[{0}] Water chart rows are not strictly increasing: {1}").format(
						FMS_M605, "; ".join(water_errors)
					),
				)

	def _compute_maxima(self) -> None:
		if self.rows:
			self.max_depth_mm = self.rows[-1].depth_mm
			self.max_volume_l = self.rows[-1].volume_l

	def _warn_capacity_mismatch(self) -> None:
		if not (self.tank and self.max_volume_l):
			return
		capacity = frappe.db.get_value("Fuel Tank", self.tank, "capacity_l")
		if not capacity:
			return
		diff_pct = abs(self.max_volume_l - capacity) / capacity * 100
		if diff_pct > 2:
			frappe.msgprint(
				_("Chart max volume {0} L differs from tank capacity {1} L by {2:.1f}%.").format(
					self.max_volume_l, capacity, diff_pct
				),
				indicator="orange",
				alert=True,
			)
