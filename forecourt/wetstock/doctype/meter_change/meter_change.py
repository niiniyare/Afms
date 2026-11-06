"""Meter Change controller (FMS-E08)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MeterChange(Document):
	def on_submit(self) -> None:
		"""Snapshot old nozzle readings, update to new start values, write NLE."""
		from forecourt.posting import ledgers as posting_ledgers

		nozzle = frappe.get_doc("Nozzle", self.nozzle)
		self.db_set("old_final_ecash", flt(nozzle.last_ecash), update_modified=False)
		self.db_set("old_final_evol", flt(nozzle.last_evol), update_modified=False)
		self.db_set("old_final_mvol", flt(nozzle.last_mvol), update_modified=False)

		frappe.flags.fms_meter_change = True
		try:
			frappe.db.set_value(
				"Nozzle",
				self.nozzle,
				{
					"last_ecash": flt(self.new_start_ecash),
					"last_evol": flt(self.new_start_evol),
					"last_mvol": flt(self.new_start_mvol),
				},
			)
		finally:
			frappe.flags.fms_meter_change = False

		posting_ledgers.write_meter_change_nozzle_ledger(self)

	def on_cancel(self) -> None:
		"""Restore nozzle last readings to old final values."""
		frappe.flags.fms_meter_change = True
		try:
			frappe.db.set_value(
				"Nozzle",
				self.nozzle,
				{
					"last_ecash": flt(self.old_final_ecash),
					"last_evol": flt(self.old_final_evol),
					"last_mvol": flt(self.old_final_mvol),
				},
			)
		finally:
			frappe.flags.fms_meter_change = False
