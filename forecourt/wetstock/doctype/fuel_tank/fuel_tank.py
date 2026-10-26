import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M604, FMS_M608, FMSValidationError


class FuelTank(Document):
	def validate(self) -> None:
		self._validate_item_is_fuel()
		self._validate_capacity()

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
