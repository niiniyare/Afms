from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class CustomerVehicle(Document):
	def validate(self) -> None:
		self._normalise_plate()

	def _normalise_plate(self) -> None:
		if self.plate_no:
			self.plate_no = self.plate_no.upper().replace(" ", "")
