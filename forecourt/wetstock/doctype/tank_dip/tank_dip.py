"""Tank Dip controller — spot dip (FMS-E06)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime

from forecourt.calc.calibration import interpolate


class TankDip(Document):
	def before_insert(self) -> None:
		self._fill_dip_entry_mode()

	def validate(self) -> None:
		self._fill_dip_entry_mode()
		self._compute_volumes()
		self._compute_book_volume()
		self._compute_difference()

	def _fill_dip_entry_mode(self) -> None:
		if self.tank:
			mode = frappe.db.get_value("Fuel Tank", self.tank, "dip_entry_mode")
			self.dip_entry_mode = mode or "Litres"

	def _compute_volumes(self) -> None:
		"""In chart mode, interpolate volume from calibration chart."""
		if self.dip_entry_mode != "Chart":
			return
		chart = frappe.get_all(
			"Tank Calibration Chart",
			filters={"tank": self.tank, "docstatus": 1},
			order_by="valid_from desc",
			limit=1,
			fields=["name"],
		)
		if not chart:
			return
		rows = frappe.get_all(
			"Tank Calibration Row",
			filters={"parent": chart[0].name},
			fields=["depth_mm", "volume_l"],
			order_by="depth_mm asc",
		)
		pairs = [(r.depth_mm, r.volume_l) for r in rows]
		if pairs and self.dip_mm:
			self.volume_l = flt(interpolate(flt(self.dip_mm), pairs), 3)
		if pairs and self.water_mm:
			self.water_l = flt(interpolate(flt(self.water_mm), pairs), 3)

	def _compute_book_volume(self) -> None:
		"""Query SLE to compute book volume at dipped_at time."""
		if not self.tank or not self.dipped_at:
			return
		tank_doc = frappe.get_cached_doc("Fuel Tank", self.tank)
		warehouse = getattr(tank_doc, "warehouse", None)
		if not warehouse:
			return
		result = frappe.db.sql(
			"""SELECT SUM(actual_qty) as book
			   FROM `tabStock Ledger Entry`
			   WHERE warehouse = %s
			     AND posting_datetime <= %s
			     AND is_cancelled = 0""",
			(warehouse, get_datetime(self.dipped_at)),
			as_dict=True,
		)
		self.book_volume_l = flt((result[0].book or 0.0), 3) if result else 0.0

	def on_submit(self) -> None:
		from forecourt.posting import ledgers as posting_ledgers

		posting_ledgers.write_spot_dip_wetstock_ledger(self)

	def _compute_difference(self) -> None:
		net_volume = flt(self.volume_l) - flt(self.water_l)
		self.difference_l = flt(net_volume - flt(self.book_volume_l), 3)
