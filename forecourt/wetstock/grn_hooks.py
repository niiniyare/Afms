"""doc_events handlers for Purchase Receipt (FMS delivery dips, E03)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.calc.calibration import interpolate
from forecourt.errors import FMS_T205, FMS_T206, FMSValidationError

_TOLERANCE_PCT = 0.5


def _get_station(doc) -> str | None:
	"""Return the station from the accounting dimension or None."""
	station = getattr(doc, "station", None)
	if station:
		return station
	if doc.name:
		return frappe.db.get_value("Purchase Receipt", doc.name, "station")
	return None


def validate_purchase_receipt(doc, method=None) -> None:
	"""Compute dip-derived volumes and enforce tolerance/dip-required gates."""
	if not doc.get("fms_delivery_dips"):
		_check_dips_required(doc)
		return

	for row in doc.fms_delivery_dips:
		_compute_dip_row(doc, row)
		_check_tolerance(row)


def _check_dips_required(doc) -> None:
	"""Raise FMS-T206 if the station requires dips but none exist for fuel lines."""
	station = _get_station(doc)
	if not station:
		return
	requires_dips = frappe.db.get_value("Station", station, "dips_required") or 0
	if not requires_dips:
		return
	for item in doc.items:
		is_fuel = frappe.db.get_value("Item", item.item_code, "fms_is_fuel") or 0
		if is_fuel:
			raise FMSValidationError(
				FMS_T206,
				_(
					"[FMS-T206] GRN {0}: station requires delivery dips but none recorded "
					"for item {1}. Add dip rows before submitting."
				).format(doc.name or "draft", item.item_code),
			)


def _compute_dip_row(doc, row) -> None:
	"""Fill received_l, invoiced_l, variance_l, variance_pct on one dip row."""
	tank = frappe.get_cached_doc("Fuel Tank", row.tank) if row.tank else None
	if tank:
		row.dip_entry_mode = tank.dip_entry_mode or "Litres"
	else:
		row.dip_entry_mode = "Litres"

	if row.dip_entry_mode == "Chart":
		chart = frappe.get_all(
			"Tank Calibration Chart",
			filters={"tank": row.tank, "docstatus": 1},
			order_by="valid_from desc",
			limit=1,
			fields=["name"],
		)
		if chart:
			chart_rows = frappe.get_all(
				"Tank Calibration Row",
				filters={"parent": chart[0].name},
				fields=["depth_mm", "volume_l"],
				order_by="depth_mm asc",
			)
			pairs = [(r.depth_mm, r.volume_l) for r in chart_rows]
			if pairs:
				row.volume_before_l = flt(interpolate(flt(row.dip_before_mm), pairs), 3)
				row.volume_after_l = flt(interpolate(flt(row.dip_after_mm), pairs), 3)

	sales = flt(row.sales_during_drop_l)
	row.received_l = flt(flt(row.volume_after_l) - flt(row.volume_before_l) + sales, 3)

	invoiced = 0.0
	for item in doc.items:
		if item.warehouse and row.tank:
			tank_warehouse = frappe.db.get_value("Fuel Tank", row.tank, "warehouse")
			if item.warehouse == tank_warehouse:
				invoiced += flt(item.qty)
	row.invoiced_l = flt(invoiced, 3)

	if row.invoiced_l:
		row.variance_l = flt(row.received_l - row.invoiced_l, 3)
		row.variance_pct = flt(row.variance_l / row.invoiced_l * 100, 4)
	else:
		row.variance_l = 0.0
		row.variance_pct = 0.0


def _check_tolerance(row) -> None:
	"""Raise FMS-T205 if variance exceeds tolerance and no reason given."""
	if not row.invoiced_l:
		return
	abs_var_pct = abs(flt(row.variance_pct))
	if abs_var_pct > _TOLERANCE_PCT and not row.reason:
		raise FMSValidationError(
			FMS_T205,
			_(
				"[FMS-T205] Delivery dip for tank {0}: variance {1:.2f}% exceeds {2}% tolerance. "
				"Select a Variance Reason before submitting."
			).format(row.tank, flt(row.variance_pct), _TOLERANCE_PCT),
		)


def on_submit_purchase_receipt(doc, method=None) -> None:
	"""Placeholder: Wetstock Ledger Entry (Delivery) wired in FMS-F15."""
	pass


def on_cancel_purchase_receipt(doc, method=None) -> None:
	"""Placeholder: cancel/block wired in FMS-F15."""
	pass
