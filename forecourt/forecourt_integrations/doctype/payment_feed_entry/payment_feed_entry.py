"""Payment Feed Entry controller — FMS-J04."""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class PaymentFeedEntry(Document):
	def validate(self) -> None:
		self._validate_unique_reference()

	def _validate_unique_reference(self) -> None:
		if not self.provider or not self.reference:
			return
		existing = frappe.db.get_value(
			"Payment Feed Entry",
			{"provider": self.provider, "reference": self.reference},
			"name",
		)
		if existing and existing != self.name:
			frappe.throw(
				f"Duplicate reference {self.reference} for provider {self.provider} (existing: {existing})."
			)
