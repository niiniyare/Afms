"""Tank Transfer controller (FMS-E07)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_date_str, get_datetime, get_time_str


class TankTransfer(Document):
	def validate(self) -> None:
		self._validate_tanks()

	def on_submit(self) -> None:
		self._create_stock_entry()

	def on_cancel(self) -> None:
		self._cancel_stock_entry()

	def _validate_tanks(self) -> None:
		if self.from_tank == self.to_tank:
			frappe.throw(_("From Tank and To Tank must be different."))

		from_item = frappe.db.get_value("Fuel Tank", self.from_tank, "item")
		to_item = frappe.db.get_value("Fuel Tank", self.to_tank, "item")
		if from_item != to_item:
			frappe.throw(
				_(
					"Tank Transfer only allowed between tanks with the same product. From: {0}, To: {1}."
				).format(from_item, to_item)
			)

		from_station = frappe.db.get_value("Fuel Tank", self.from_tank, "station")
		to_station = frappe.db.get_value("Fuel Tank", self.to_tank, "station")
		if from_station != to_station:
			frappe.throw(
				_("Tank Transfer only allowed within the same station. From: {0}, To: {1}.").format(
					from_station, to_station
				)
			)

	def _create_stock_entry(self) -> None:
		from_doc = frappe.get_doc("Fuel Tank", self.from_tank)
		to_doc = frappe.get_doc("Fuel Tank", self.to_tank)
		company = frappe.db.get_value("Station", self.station, "company")
		dt = get_datetime(self.transferred_at)

		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Transfer",
				"company": company,
				"posting_date": get_date_str(dt),
				"posting_time": get_time_str(dt),
				"remarks": _("Tank Transfer {0}: {1} L from {2} to {3}").format(
					self.name, flt(self.volume_l), self.from_tank, self.to_tank
				),
				"items": [
					{
						"item_code": from_doc.item,
						"qty": flt(self.volume_l),
						"s_warehouse": from_doc.warehouse,
						"t_warehouse": to_doc.warehouse,
					}
				],
			}
		)
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		self.db_set("stock_entry", se.name)

	def _cancel_stock_entry(self) -> None:
		if not self.stock_entry:
			return
		se_doc = frappe.get_doc("Stock Entry", self.stock_entry)
		if se_doc.docstatus == 1:
			se_doc.flags.ignore_permissions = True
			se_doc.cancel()
