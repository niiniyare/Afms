"""Forecourt Shift controller.

F01: DocType structure (no logic).
F02: before_insert pre-fill.
F03+: validate, before_submit, on_submit (added in later tasks).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime


class ForecourtShift(Document):
	# ------------------------------------------------------------------ F02
	def before_insert(self) -> None:
		"""Pre-fill the shift from the template and previous shift."""
		self._find_previous_shift()
		self._snapshot_station_settings()
		self._compute_shift_window()
		self._create_price_rows()
		self._create_reading_rows()
		self._create_tank_rows()
		self._set_title()

	# ------------------------------------------------------------------ helpers

	def _find_previous_shift(self) -> None:
		prev = frappe.get_all(
			"Forecourt Shift",
			filters={"station": self.station, "docstatus": 1},
			fields=["name"],
			order_by="shift_start desc",
			limit=1,
		)
		self.previous_shift = prev[0].name if prev else None

	def _snapshot_station_settings(self) -> None:
		if not self.station:
			return
		station = frappe.get_cached_doc("Station", self.station)
		self.dip_entry_mode = getattr(station, "dip_entry_mode", None) or "Litres"
		self.sales_basis = getattr(station, "sales_basis", None) or "Elec Cash"
		self.price_change_mode = getattr(station, "price_change_mode", None) or "Latest price"
		self.record_elec_cash = int(getattr(station, "record_elec_cash", 1) or 1)
		self.record_elec_meter = int(getattr(station, "record_elec_meter", 0) or 0)
		self.record_man_meter = int(getattr(station, "record_man_meter", 0) or 0)

	def _compute_shift_window(self) -> None:
		if not self.shift_template or not self.shift_date:
			return
		tpl = frappe.get_cached_doc("Forecourt Shift Template", self.shift_template)
		from datetime import date, datetime, time, timedelta

		def _combine(d, t) -> datetime:
			if isinstance(d, str):
				d = date.fromisoformat(d)
			if isinstance(t, str):
				h, m, s = [*t.split(":"), "0"][:3]
				t = time(int(h), int(m), int(float(s)))
			return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)

		if not self.shift_start:
			self.shift_start = _combine(self.shift_date, tpl.start_time)
		end_dt = _combine(self.shift_date, tpl.end_time)
		start_dt = get_datetime(self.shift_start)
		# overnight: end <= start means end is the next day
		if end_dt <= start_dt:
			end_dt = end_dt + timedelta(days=1)
		if not self.shift_end:
			self.shift_end = end_dt

	def _create_price_rows(self) -> None:
		if not self.station:
			return
		station = frappe.get_cached_doc("Station", self.station)
		price_list = getattr(station, "price_list", None)
		if not price_list:
			return

		fuel_items = frappe.get_all(
			"Item",
			filters={"fms_is_fuel": 1},
			fields=["name"],
		)
		for fuel in fuel_items:
			price = frappe.db.get_value(
				"Item Price",
				{"item_code": fuel.name, "price_list": price_list, "selling": 1},
				"price_list_rate",
			)
			if price:
				self.append(
					"prices",
					{
						"item": fuel.name,
						"segment_no": 1,
						"price": flt(price),
						"effective_from": self.shift_start,
						"effective_to": None,
					},
				)

	def _create_reading_rows(self) -> None:
		"""Create one Shift Meter Reading row per nozzle from the template."""
		if not self.shift_template:
			return
		tpl = frappe.get_cached_doc("Forecourt Shift Template", self.shift_template)
		station = frappe.get_cached_doc("Station", self.station) if self.station else None

		for nozzle_row in tpl.nozzle_assignments:
			nozzle = frappe.get_cached_doc("Nozzle", nozzle_row.nozzle)
			pump = frappe.get_cached_doc("Pump", nozzle.pump) if nozzle.pump else None

			rec_ecash = int(
				(getattr(pump, "record_elec_cash", None) if pump else None)
				or (getattr(station, "record_elec_cash", 1) or 1)
			)
			rec_evol = int(
				(getattr(pump, "record_elec_meter", None) if pump else None)
				or (getattr(station, "record_elec_meter", 0) or 0)
			)
			rec_mvol = int(
				(getattr(pump, "record_man_meter", None) if pump else None)
				or (getattr(station, "record_man_meter", 0) or 0)
			)
			sales_basis = (
				(getattr(pump, "sales_basis", None) if pump else None)
				or (getattr(station, "sales_basis", None) if station else None)
				or "Elec Cash"
			)

			price = self._get_price_for_item(nozzle.item) if nozzle.item else None

			self.append(
				"meter_readings",
				{
					"nozzle": nozzle_row.nozzle,
					"tank": nozzle.tank,
					"item": nozzle.item,
					"cashier": nozzle_row.cashier,
					"attendant": nozzle_row.attendant,
					"segment_no": 1,
					"price": flt(price) if price else 0.0,
					"rec_elec_cash": rec_ecash,
					"rec_elec_meter": rec_evol,
					"rec_man_meter": rec_mvol,
					"row_sales_basis": sales_basis,
					"opening_elec_cash": flt(nozzle.last_ecash),
					"opening_elec_meter": flt(nozzle.last_evol),
					"opening_man_meter": flt(nozzle.last_mvol),
					"source": "Manual",
				},
			)

	def _create_tank_rows(self) -> None:
		"""Create one Shift Tank Dip row per active tank at the station."""
		if not self.station:
			return
		tanks = frappe.get_all(
			"Fuel Tank",
			filters={"station": self.station, "status": "Active"},
			fields=["name", "item", "dip_entry_mode", "opening_dip_l"],
		)
		station = frappe.get_cached_doc("Station", self.station)
		station_dip_mode = getattr(station, "dip_entry_mode", "Litres") or "Litres"

		for tank in tanks:
			dip_mode = tank.dip_entry_mode or station_dip_mode
			opening_l = self._get_previous_closing_dip(tank.name)
			if opening_l is None:
				opening_l = flt(tank.opening_dip_l)

			self.append(
				"tank_dips",
				{
					"tank": tank.name,
					"item": tank.item,
					"dip_entry_mode": dip_mode,
					"opening_l": flt(opening_l),
					"source": "Manual",
				},
			)

	def _get_previous_closing_dip(self, tank: str) -> float | None:
		if not self.previous_shift:
			return None
		result = frappe.get_all(
			"Shift Tank Dip",
			filters={"parent": self.previous_shift, "tank": tank},
			fields=["dip_l"],
			limit=1,
		)
		return flt(result[0].dip_l) if result else None

	def _get_price_for_item(self, item: str) -> float | None:
		for row in self.prices:
			if row.item == item:
				return flt(row.price)
		return None

	def _set_title(self) -> None:
		if self.station and self.shift_template and self.shift_date:
			station_label = frappe.db.get_value("Station", self.station, "station_name") or self.station
			self.shift_title = f"{station_label} · {self.shift_template} · {self.shift_date}"
