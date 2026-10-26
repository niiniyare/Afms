"""Fuel Price Change controller (FMS-E09, FMS-F07)."""

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
		self._apply_to_open_shift()  # F07: add price segment to open shift

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

	def _apply_to_open_shift(self) -> None:
		"""Split price segments in the open shift at this station (F07).

		Only runs when the station's price_change_mode is
		"Latest price with segments".
		"""
		if not self.station:
			return
		station_doc = frappe.get_cached_doc("Station", self.station)
		if getattr(station_doc, "price_change_mode", None) != "Latest price with segments":
			return

		open_shift_name = frappe.db.get_value(
			"Forecourt Shift",
			{"station": self.station, "docstatus": 0},
			"name",
			order_by="shift_start desc",
		)
		if not open_shift_name:
			return

		shift = frappe.get_doc("Forecourt Shift", open_shift_name)
		effective_dt = get_datetime(self.effective_at)

		# effective_at must fall within the shift window
		if not (get_datetime(shift.shift_start) <= effective_dt < get_datetime(shift.shift_end)):
			return

		changed = False
		for fpc_item in self.items:
			item = fpc_item.item
			new_price = flt(fpc_item.new_price)

			# Find latest price segment for this item
			current_rows = [r for r in shift.prices if r.item == item]
			if not current_rows:
				continue
			cur_price_row = max(current_rows, key=lambda r: flt(r.segment_no) or 0)
			current_segment = int(cur_price_row.segment_no or 1)
			new_segment = current_segment + 1

			# Close the current segment
			cur_price_row.effective_to = effective_dt

			# Add new price row
			shift.append(
				"prices",
				{
					"item": item,
					"segment_no": new_segment,
					"price": new_price,
					"effective_from": effective_dt,
					"effective_to": None,
					"fuel_price_change": self.name,
				},
			)

			# Split meter reading rows for this item's nozzles
			nozzles_in_segment = {
				r.nozzle
				for r in shift.meter_readings
				if r.item == item and int(r.segment_no or 1) == current_segment
			}
			for nozzle in nozzles_in_segment:
				nozzle_rows = [
					r
					for r in shift.meter_readings
					if r.nozzle == nozzle and int(r.segment_no or 1) == current_segment
				]
				if not nozzle_rows:
					continue
				cur_row = nozzle_rows[-1]
				# Clear closing readings so manager enters them at change time
				cur_row.closing_elec_cash = None
				cur_row.closing_elec_meter = None
				cur_row.closing_man_meter = None
				# Add new row for next segment (openings filled by manager)
				shift.append(
					"meter_readings",
					{
						"nozzle": nozzle,
						"tank": cur_row.tank,
						"item": item,
						"cashier": cur_row.cashier,
						"attendant": cur_row.attendant,
						"segment_no": new_segment,
						"price": new_price,
						"rec_elec_cash": cur_row.rec_elec_cash,
						"rec_elec_meter": cur_row.rec_elec_meter,
						"rec_man_meter": cur_row.rec_man_meter,
						"row_sales_basis": cur_row.row_sales_basis,
						"source": "Manual",
					},
				)
			changed = True

		if changed:
			shift.flags.ignore_validate = True
			shift.save(ignore_permissions=True)
			frappe.db.set_value(
				"Fuel Price Change",
				self.name,
				"applied_to_shift",
				open_shift_name,
				update_modified=False,
			)
