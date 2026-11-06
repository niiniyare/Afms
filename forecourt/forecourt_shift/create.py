"""FMS-U05: New Shift dialog — server defaults and creation pre-flight.

Codes used:
  FMS-S116  Another draft shift is open at this station.
  FMS-S117  Previous shift is not yet closed.
  FMS-S118  No price for a fuel item at this station on the shift date.
  FMS-S119  No active shift template for this station.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, format_datetime, getdate, today

from forecourt.errors import FMS_S116, FMS_S117, FMS_S118, FMS_S119


@frappe.whitelist()
def get_new_shift_defaults(station: str | None = None) -> dict:
	"""Return pre-filled defaults for the New Shift dialog.

	If *station* is not given, the caller's default station (User Permission
	``is_default=1``) is used.  Returns an empty dict when no station can be
	determined.
	"""
	if not station:
		station = _user_default_station()
	if not station:
		return {}

	last = _last_submitted_shift(station)
	return {
		"station": station,
		"next_template": _next_template(station, last),
		"next_date": _next_shift_date(last),
		"previous_shift_label": _prev_shift_label(last),
	}


@frappe.whitelist()
def create_shift(station: str, shift_template: str, shift_date: str) -> dict:
	"""Pre-flight checks then insert a new Forecourt Shift.

	Raises coded ``frappe.ValidationError`` for each pre-flight failure so the
	dialog can display the message inline without creating anything.

	Returns ``{"shift": shift.name}`` on success.
	"""
	frappe.has_permission("Forecourt Shift", "create", throw=True)

	# S119: template must be active at this station.
	tpl_exists = frappe.db.exists(
		"Forecourt Shift Template",
		{"name": shift_template, "station": station, "active": 1},
	)
	if not tpl_exists:
		frappe.throw(
			_("[{0}] {1} has no active shift template named {2}. Ask the administrator to add one.").format(
				FMS_S119, station, shift_template
			),
			title=_("Cannot Create Shift"),
		)

	# S116: no other draft shift open at this station.
	open_shift = frappe.db.get_value(
		"Forecourt Shift",
		{"station": station, "docstatus": 0, "status": ["not in", ["Closed", "Corrected"]]},
		"name",
	)
	if open_shift:
		frappe.throw(
			_(
				"[{0}] Shift {1} is already open at {2}. "
				"Close it before opening another one, or open it to continue."
			).format(FMS_S116, open_shift, station),
			title=_("Cannot Create Shift"),
		)

	# S117: last non-cancelled shift must be submitted (docstatus = 1).
	last_draft = frappe.db.get_value(
		"Forecourt Shift",
		{"station": station, "docstatus": 0},
		["name", "status"],
		order_by="shift_start desc",
		as_dict=True,
	)
	if last_draft:
		frappe.throw(
			_(
				"[{0}] The previous shift {1} is not closed yet. "
				"Its closing values are this shift's openings. Close it first."
			).format(FMS_S117, last_draft.name),
			title=_("Cannot Create Shift"),
		)

	# S118: at least one active fuel item at this station must have a price.
	_check_fuel_prices(station, shift_date, shift_template)

	shift = frappe.get_doc(
		{
			"doctype": "Forecourt Shift",
			"station": station,
			"shift_template": shift_template,
			"shift_date": getdate(shift_date),
		}
	)
	shift.insert()
	return {"shift": shift.name}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _user_default_station() -> str | None:
	rows = frappe.get_all(
		"User Permission",
		filters={"user": frappe.session.user, "allow": "Station", "is_default": 1},
		fields=["for_value"],
		limit=1,
	)
	return rows[0].for_value if rows else None


def _last_submitted_shift(station: str) -> object | None:
	rows = frappe.get_all(
		"Forecourt Shift",
		filters={"station": station, "docstatus": 1},
		fields=["name", "shift_template", "shift_end", "shift_date"],
		order_by="shift_start desc",
		limit=1,
	)
	return rows[0] if rows else None


def _next_template(station: str, last_shift: object | None) -> str | None:
	templates = frappe.get_all(
		"Forecourt Shift Template",
		filters={"station": station, "active": 1},
		fields=["name", "sequence"],
		order_by="sequence asc",
	)
	if not templates:
		return None
	if not last_shift or not last_shift.shift_template:
		return templates[0].name
	# Find the template after the last one by sequence, wrap around.
	last_seq = next(
		(t.sequence for t in templates if t.name == last_shift.shift_template),
		None,
	)
	if last_seq is None:
		return templates[0].name
	for t in templates:
		if (t.sequence or 0) > (last_seq or 0):
			return t.name
	return templates[0].name  # wrap to first


def _next_shift_date(last_shift: object | None) -> str:
	if last_shift and last_shift.shift_date:
		return str(add_days(last_shift.shift_date, 1))
	return today()


def _prev_shift_label(last_shift: object | None) -> str:
	if not last_shift:
		return ""
	closed_at = format_datetime(last_shift.shift_end, "dd MMM HH:mm") if last_shift.shift_end else ""
	return _("Opens from {0}{1}").format(
		last_shift.name,
		f", closed {closed_at}" if closed_at else "",
	)


def _check_fuel_prices(station: str, shift_date: str, shift_template: str) -> None:
	"""S118: every active fuel item assigned to this template must have a price."""
	station_doc = frappe.get_cached_doc("Station", station)
	price_list = getattr(station_doc, "price_list", None)
	if not price_list:
		return  # price list not configured; before_insert handles this case

	# Collect items from the template's nozzle assignments.
	nozzle_rows = frappe.get_all(
		"Shift Template Nozzle",
		filters={"parent": shift_template},
		fields=["nozzle"],
	)
	if not nozzle_rows:
		return

	items: set[str] = set()
	for n in nozzle_rows:
		item = n.nozzle and frappe.db.get_value("Nozzle", n.nozzle, "item")
		if item:
			items.add(item)
	if not items:
		return

	from frappe.query_builder import DocType as QBDocType

	ItemPrice = QBDocType("Item Price")
	ref_date = str(shift_date)
	missing = []
	for item in sorted(items):
		rows = (
			frappe.qb.from_(ItemPrice)
			.select(ItemPrice.price_list_rate)
			.where(ItemPrice.item_code == item)
			.where(ItemPrice.price_list == price_list)
			.where(ItemPrice.selling == 1)
			.where((ItemPrice.valid_from.isnull()) | (ItemPrice.valid_from <= ref_date))
			.limit(1)
			.run(as_dict=True)
		)
		if not rows or not rows[0].price_list_rate:
			missing.append(item)

	if missing:
		frappe.throw(
			_(
				"[{0}] No price found for {1} at {2} on {3}. Post a Fuel Price Change, then create the shift."
			).format(FMS_S118, ", ".join(missing), station, ref_date),
			title=_("Cannot Create Shift"),
		)
