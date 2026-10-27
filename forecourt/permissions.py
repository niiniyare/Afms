"""
FMS row-level permission helpers — design guide 14.2.

User Permission on Station Group expands to all descendant stations.
User Permission on Station restricts directly to named stations.

All FMS DocTypes with a ``station`` field register ``has_station_permission``
as their ``has_permission`` hook, and a per-doctype ``_*_query`` wrapper as
their ``permission_query_conditions`` hook.
"""

from __future__ import annotations

import frappe


def get_permitted_stations(user: str) -> list[str] | None:
	"""
	Return the station names accessible to *user*, or ``None`` (no restriction).

	Priority:
	1. Explicit Station User Permission — use as-is.
	2. Station Group User Permission — expand to all stations in those
	   groups and their descendants.
	3. Neither set — return ``None`` (no restriction).
	"""
	all_perms = frappe.permissions.get_user_permissions(user)

	station_perms = all_perms.get("Station", [])
	if station_perms:
		return [p.get("doc") for p in station_perms if p.get("doc")]

	group_perms = all_perms.get("Station Group", [])
	if not group_perms:
		return None

	permitted_groups = [p.get("doc") for p in group_perms if p.get("doc")]
	if not permitted_groups:
		return []

	if not frappe.db.table_exists("Station Group") or not frappe.db.table_exists("Station"):
		return None

	all_group_names: set[str] = set()
	for group_name in permitted_groups:
		root = frappe.db.get_value("Station Group", group_name, ["lft", "rgt"], as_dict=True)
		if not root:
			continue
		descendants = frappe.get_all(
			"Station Group",
			filters={"lft": [">=", root.lft], "rgt": ["<=", root.rgt]},
			pluck="name",
		)
		all_group_names.update(descendants)

	if not all_group_names:
		return []

	return frappe.get_all(
		"Station",
		filters={"station_group": ["in", list(all_group_names)]},
		pluck="name",
	)


def has_station_permission(doc: "frappe.Document", ptype: str, user: str) -> bool | None:
	"""
	Generic ``has_permission`` hook for FMS DocTypes that carry a ``station`` field.
	Works for Station itself (where the station IS the document name).

	Returns ``True`` if the station is in the user's permitted set,
	``None`` to continue standard checks (no Station/Group permission set),
	and implicitly ``False`` via ``None`` → deny when the set is empty.
	"""
	if ptype not in ("read", "select"):
		return None

	if doc.doctype == "Station":
		station = doc.name
	else:
		station = doc.get("station")

	if not station:
		return None

	stations = get_permitted_stations(user)
	if stations is None:
		return None

	return True if station in stations else None


# ---------------------------------------------------------------------------
# Shared query helper
# ---------------------------------------------------------------------------


def _station_query(doctype: str, user: str, station_field: str = "station") -> str:
	stations = get_permitted_stations(user)
	if stations is None:
		return ""
	if not stations:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(s) for s in stations)
	return f"`tab{doctype}`.`{station_field}` IN ({escaped})"


# ---------------------------------------------------------------------------
# Per-DocType permission_query_conditions wrappers
# ---------------------------------------------------------------------------


def station_query(user: str) -> str:
	return _station_query("Station", user, station_field="name")


def fuel_tank_query(user: str) -> str:
	return _station_query("Fuel Tank", user)


def pump_query(user: str) -> str:
	return _station_query("Pump", user)


def island_query(user: str) -> str:
	return _station_query("Island", user)


def nozzle_query(user: str) -> str:
	return _station_query("Nozzle", user)


def tank_calibration_chart_query(user: str) -> str:
	return _station_query("Tank Calibration Chart", user)


def meter_change_query(user: str) -> str:
	return _station_query("Meter Change", user)


def tank_dip_query(user: str) -> str:
	return _station_query("Tank Dip", user)


def tank_transfer_query(user: str) -> str:
	return _station_query("Tank Transfer", user)


def forecourt_shift_template_query(user: str) -> str:
	return _station_query("Forecourt Shift Template", user)


def fuel_price_change_query(user: str) -> str:
	return _station_query("Fuel Price Change", user)


def forecourt_shift_query(user: str) -> str:
	return _station_query("Forecourt Shift", user)


def shift_correction_query(user: str) -> str:
	return _station_query("Shift Correction", user)


def wetstock_ledger_entry_query(user: str) -> str:
	return _station_query("Wetstock Ledger Entry", user)


def nozzle_ledger_entry_query(user: str) -> str:
	return _station_query("Nozzle Ledger Entry", user)


def sales_ledger_entry_query(user: str) -> str:
	return _station_query("Sales Ledger Entry", user)


def cashier_ledger_entry_query(user: str) -> str:
	return _station_query("Cashier Ledger Entry", user)
