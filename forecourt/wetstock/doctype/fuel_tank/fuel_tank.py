import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M604, FMS_M608, FMS_M610, FMSValidationError

_OPENING_DIP_FIELDS: frozenset[str] = frozenset(["opening_dip_date", "opening_dip_l"])


class FuelTank(Document):
	def validate(self) -> None:
		self._validate_item_is_fuel()
		self._validate_capacity()
		self._validate_opening_dip()

	def after_insert(self) -> None:
		from forecourt.setup.fuel_tank_warehouse import create_tank_warehouse

		create_tank_warehouse(self)

	def on_trash(self) -> None:
		if self.warehouse and frappe.db.exists("Stock Ledger Entry", {"warehouse": self.warehouse}):
			raise FMSValidationError(
				FMS_M608,
				_("Fuel Tank {0} cannot be deleted: it has stock history in {1}.").format(
					self.name, self.warehouse
				),
			)

	def _validate_item_is_fuel(self) -> None:
		if self.item and not frappe.db.get_value("Item", self.item, "fms_is_fuel"):
			raise FMSValidationError(
				FMS_M604,
				_("[{0}] Item {1} is not marked as fuel. Tick Is Fuel on the item.").format(
					FMS_M604, self.item
				),
			)

	def _validate_opening_dip(self) -> None:
		if self.flags.get("from_fms"):
			return
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changed = any(getattr(self, f) != getattr(before, f, None) for f in _OPENING_DIP_FIELDS)
		if not changed:
			return
		if self.warehouse and frappe.db.exists("Stock Ledger Entry", {"warehouse": self.warehouse}):
			raise FMSValidationError(
				FMS_M610,
				_("[{0}] Opening dip cannot be changed after stock has been recorded for this tank.").format(
					FMS_M610
				),
			)

	def _validate_capacity(self) -> None:
		if self.capacity_l is not None and self.capacity_l <= 0:
			raise FMSValidationError(
				FMS_M604,
				_("[{0}] Capacity must be greater than zero.").format(FMS_M604),
			)
		if self.safe_fill_l and self.capacity_l and self.safe_fill_l > self.capacity_l:
			raise FMSValidationError(
				FMS_M604,
				_("[{0}] Safe fill ({1} L) cannot exceed capacity ({2} L).").format(
					FMS_M604, self.safe_fill_l, self.capacity_l
				),
			)
