"""Integration Inbox controller — FMS-J03."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class IntegrationInbox(Document):
	def validate(self) -> None:
		self._validate_unique_external_id()

	def after_insert(self) -> None:
		self._enqueue_process()

	# ------------------------------------------------------------------

	def _validate_unique_external_id(self) -> None:
		if not self.provider or not self.external_id:
			return
		existing = frappe.db.get_value(
			"Integration Inbox",
			{"provider": self.provider, "external_id": self.external_id},
			"name",
		)
		if existing and existing != self.name:
			frappe.throw(
				_("Duplicate external_id {0} for provider {1} (existing row: {2}).").format(
					self.external_id, self.provider, existing
				)
			)

	def _enqueue_process(self) -> None:
		frappe.enqueue(
			"forecourt.forecourt_integrations.inbox_processor.process",
			inbox_name=self.name,
			queue="default",
			timeout=120,
			now=frappe.flags.in_test,
		)
