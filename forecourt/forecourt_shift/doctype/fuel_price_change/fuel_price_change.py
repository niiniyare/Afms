"""Fuel Price Change controller (FMS-E09)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, now_datetime


class FuelPriceChange(Document):
	def validate(self) -> None:
		self._validate_effective_at()
		self._fill_old_prices()

	def before_submit(self) -> None:
		self._validate_effective_at()
		if self.approval_state != "Approved":
			frappe.throw(_("Fuel Price Change must be Approved before submitting."))

	def on_submit(self) -> None:
		self._write_item_prices()

	def on_cancel(self) -> None:
		if self.applied_to_shift:
			shift_status = frappe.db.get_value("Forecourt Shift", self.applied_to_shift, "status")
			if shift_status == "Closed":
				from forecourt.errors import FMS_C502, FMSValidationError

				raise FMSValidationError(
					FMS_C502,
					_(
						"Fuel Price Change {0} is linked to a Closed shift and cannot "
						"be cancelled directly. Use Shift Correction."
					).format(self.name),
				)

	def _validate_effective_at(self) -> None:
		if not self.effective_at:
			return
		if get_datetime(self.effective_at) > now_datetime():
			frappe.throw(
				_(
					"Effective At may not be in the future. "
					"Set it to the time the price change actually took effect."
				)
			)

	def _fill_old_prices(self) -> None:
		"""Populate old_price from the current Item Price on the station price list."""
		if not self.station:
			return
		station_doc = frappe.get_cached_doc("Station", self.station)
		price_list = getattr(station_doc, "price_list", None)
		for item_row in self.items:
			if not item_row.old_price and price_list and item_row.item:
				price = frappe.db.get_value(
					"Item Price",
					{"item_code": item_row.item, "price_list": price_list, "selling": 1},
					"price_list_rate",
				)
				if price:
					item_row.old_price = flt(price)

	def _write_item_prices(self) -> None:
		"""Write Item Price records on the station price list."""
		if not self.station:
			return
		station_doc = frappe.get_cached_doc("Station", self.station)
		price_list = getattr(station_doc, "price_list", None)
		if not price_list:
			return

		effective_date = get_datetime(self.effective_at).date()
		for item_row in self.items:
			if not item_row.item or not item_row.new_price:
				continue
			existing = frappe.db.get_value(
				"Item Price",
				{
					"item_code": item_row.item,
					"price_list": price_list,
					"selling": 1,
					"valid_from": str(effective_date),
				},
				"name",
			)
			if existing:
				frappe.db.set_value("Item Price", existing, "price_list_rate", flt(item_row.new_price))
			else:
				ip = frappe.get_doc(
					{
						"doctype": "Item Price",
						"item_code": item_row.item,
						"price_list": price_list,
						"selling": 1,
						"valid_from": str(effective_date),
						"price_list_rate": flt(item_row.new_price),
					}
				)
				ip.flags.ignore_permissions = True
				ip.insert()
