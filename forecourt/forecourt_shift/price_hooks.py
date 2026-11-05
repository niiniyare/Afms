"""Price hooks for Sales Invoice and POS Invoice (FMS-E09)."""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime


def set_fuel_price_on_invoice(doc, method=None) -> None:
	"""Set rate on fuel item lines from the Fuel Price Change in force at posting time."""
	station = getattr(doc, "station", None)
	if not station:
		return

	time_str = str(getattr(doc, "posting_time", "00:00:00") or "00:00:00")
	posting_dt = get_datetime(f"{doc.posting_date} {time_str}")

	for item in doc.items:
		if not frappe.db.get_value("Item", item.item_code, "fms_is_fuel"):
			continue
		price = _get_price_at(station, item.item_code, posting_dt)
		if price:
			item.rate = flt(price, 6)


def _get_price_at(station: str, item_code: str, at_datetime) -> float | None:
	"""Return new_price from the latest Approved FPC for this station+item at or before at_datetime."""
	result = frappe.db.sql(
		"""
		SELECT fci.new_price
		FROM `tabFuel Price Change` fpc
		JOIN `tabFuel Price Change Item` fci ON fci.parent = fpc.name
		WHERE fpc.station = %s
		  AND fci.item = %s
		  AND fpc.docstatus = 1
		  AND fpc.approval_state = 'Approved'
		  AND fpc.effective_at <= %s
		ORDER BY fpc.effective_at DESC
		LIMIT 1
		""",
		(station, item_code, at_datetime),
		as_dict=True,
	)
	return flt(result[0].new_price) if result else None
