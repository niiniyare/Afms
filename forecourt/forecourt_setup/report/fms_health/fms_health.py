"""FMS Health — design guide 15.4. Daily health check across all stations."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime, nowdate


def execute(filters=None):
	return _columns(), _data(filters or {})


def _columns():
	return [
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 160},
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 120,
		},
		{"label": _("Issue"), "fieldname": "issue", "fieldtype": "Data", "width": 300},
		{
			"label": _("Document"),
			"fieldname": "document",
			"fieldtype": "Dynamic Link",
			"options": "doctype",
			"width": 160,
		},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 80},
		{"label": _("DocType"), "fieldname": "doctype", "fieldtype": "Data", "width": 0, "hidden": 1},
	]


def _data(filters: dict) -> list[dict]:
	rows: list[dict] = []
	today = getdate(nowdate())
	station_filter = filters.get("station")

	rows.extend(_check_no_shift_today(today, station_filter))
	rows.extend(_check_stale_draft_shifts(today, station_filter))
	rows.extend(_check_stale_nozzle_readings(today, station_filter))
	rows.extend(_check_tank_stock(station_filter))
	rows.extend(_check_old_clearing_items(today, station_filter))
	rows.extend(_check_failed_inbox())
	rows.extend(_check_calibration_charts(today, station_filter))

	return rows


def _check_no_shift_today(today, station_filter) -> list[dict]:
	"""Stations with no submitted shift in the last 24 hours."""
	if not frappe.db.table_exists("Forecourt Shift"):
		return []

	all_stations = _active_stations(station_filter)
	cutoff = add_days(today, -1)
	active_stations = set(
		frappe.get_all(
			"Forecourt Shift",
			filters={
				"docstatus": 1,
				"posting_date": [">=", cutoff],
			},
			pluck="station",
		)
	)
	rows = []
	for station in all_stations:
		if station not in active_stations:
			rows.append(
				{
					"category": _("No Recent Shift"),
					"station": station,
					"issue": _("No submitted shift in the last 24 hours"),
					"document": station,
					"doctype": "Station",
					"age_days": 1,
				}
			)
	return rows


def _check_stale_draft_shifts(today, station_filter) -> list[dict]:
	"""Draft shifts older than 2 days (approximate back-dating limit)."""
	if not frappe.db.table_exists("Forecourt Shift"):
		return []

	backdating_limit = 2
	cutoff = add_days(today, -backdating_limit)
	f = {"docstatus": 0, "posting_date": ["<", cutoff]}
	if station_filter:
		f["station"] = station_filter

	drafts = frappe.get_all(
		"Forecourt Shift",
		filters=f,
		fields=["name", "station", "posting_date"],
	)
	rows = []
	for d in drafts:
		age = (today - getdate(d.posting_date)).days
		rows.append(
			{
				"category": _("Stale Draft Shift"),
				"station": d.station,
				"issue": _("Draft shift {0} is {1} days old").format(d.name, age),
				"document": d.name,
				"doctype": "Forecourt Shift",
				"age_days": age,
			}
		)
	return rows


def _check_stale_nozzle_readings(today, station_filter) -> list[dict]:
	"""Nozzles with no Nozzle Ledger Entry in the last 7 days."""
	if not frappe.db.table_exists("Nozzle Ledger Entry") or not frappe.db.table_exists("Nozzle"):
		return []

	stale_days = 7
	cutoff = add_days(today, -stale_days)
	nozzle_filter = {}
	if station_filter:
		nozzle_filter["station"] = station_filter

	all_nozzles = frappe.get_all("Nozzle", filters=nozzle_filter, fields=["name", "station"])
	active_nozzles = set(
		frappe.get_all(
			"Nozzle Ledger Entry",
			filters={"posting_date": [">=", cutoff], "is_cancelled": 0},
			pluck="nozzle",
		)
	)
	rows = []
	for n in all_nozzles:
		if n.name not in active_nozzles:
			rows.append(
				{
					"category": _("Stale Nozzle"),
					"station": n.station,
					"issue": _("Nozzle {0} has no readings in the last {1} days").format(n.name, stale_days),
					"document": n.name,
					"doctype": "Nozzle",
					"age_days": stale_days,
				}
			)
	return rows


def _check_tank_stock(station_filter) -> list[dict]:
	"""Tanks whose latest book stock is below zero or above declared capacity."""
	if not frappe.db.table_exists("Wetstock Ledger Entry") or not frappe.db.table_exists("Fuel Tank"):
		return []

	tank_filter = {}
	if station_filter:
		tank_filter["station"] = station_filter

	tanks = frappe.get_all("Fuel Tank", filters=tank_filter, fields=["name", "station", "capacity_l"])
	# Latest dip per tank
	seen: set[str] = set()
	latest: dict[str, float] = {}
	rows_wle = frappe.get_all(
		"Wetstock Ledger Entry",
		filters={"entry_type": "Shift", "is_cancelled": 0, "superseded_by": ["is", "not set"]},
		fields=["tank", "dip_l"],
		order_by="posting_date desc, creation desc",
	)
	for row in rows_wle:
		t = row.tank or ""
		if t and t not in seen:
			seen.add(t)
			latest[t] = flt(row.dip_l, 3)

	rows = []
	for t in tanks:
		stock = latest.get(t.name)
		if stock is None:
			continue
		cap = flt(t.capacity_l, 3)
		if stock < 0:
			rows.append(
				{
					"category": _("Negative Stock"),
					"station": t.station,
					"issue": _("Tank {0} book stock is {1} L (below zero)").format(t.name, stock),
					"document": t.name,
					"doctype": "Fuel Tank",
					"age_days": 0,
				}
			)
		elif cap and stock > cap:
			rows.append(
				{
					"category": _("Overfull Tank"),
					"station": t.station,
					"issue": _("Tank {0} book stock {1} L exceeds capacity {2} L").format(t.name, stock, cap),
					"document": t.name,
					"doctype": "Fuel Tank",
					"age_days": 0,
				}
			)
	return rows


def _check_old_clearing_items(today, station_filter) -> list[dict]:
	"""Payment Entries that have not been bank-cleared for more than 3 days."""
	if not frappe.db.table_exists("Payment Entry"):
		return []

	age_limit = 3
	cutoff = add_days(today, -age_limit)
	f = {
		"docstatus": 1,
		"payment_type": "Receive",
		"bank_cleared_on": ["is", "not set"],
		"posting_date": ["<", cutoff],
	}
	if station_filter:
		f["fms_station"] = station_filter

	entries = frappe.get_all(
		"Payment Entry",
		filters=f,
		fields=["name", "fms_station", "posting_date"],
	)
	rows = []
	for e in entries:
		age = (today - getdate(e.posting_date)).days
		rows.append(
			{
				"category": _("Uncleared Payment"),
				"station": e.get("fms_station"),
				"issue": _("Payment Entry {0} not bank-cleared ({1} days old)").format(e.name, age),
				"document": e.name,
				"doctype": "Payment Entry",
				"age_days": age,
			}
		)
	return rows


def _check_failed_inbox() -> list[dict]:
	"""Integration Inbox messages in Failed status."""
	if not frappe.db.table_exists("Integration Inbox"):
		return []

	failed = frappe.get_all(
		"Integration Inbox",
		filters={"status": "Failed"},
		fields=["name", "creation"],
		order_by="creation asc",
		limit=50,
	)
	today = getdate(nowdate())
	rows = []
	for item in failed:
		age = (today - getdate(item.creation)).days
		rows.append(
			{
				"category": _("Failed Integration"),
				"station": None,
				"issue": _("Integration Inbox {0} is in Failed status").format(item.name),
				"document": item.name,
				"doctype": "Integration Inbox",
				"age_days": age,
			}
		)
	return rows


def _check_calibration_charts(today, station_filter) -> list[dict]:
	"""Tanks missing a calibration chart, or whose chart is expiring within 30 days."""
	if not frappe.db.table_exists("Tank Calibration Chart") or not frappe.db.table_exists("Fuel Tank"):
		return []

	warn_days = 30
	warn_date = add_days(today, warn_days)

	tank_filter = {}
	if station_filter:
		tank_filter["station"] = station_filter
	tanks = frappe.get_all("Fuel Tank", filters=tank_filter, fields=["name", "station"])

	charts = frappe.get_all(
		"Tank Calibration Chart",
		fields=["name", "tank", "valid_to"],
	)
	chart_map: dict[str, dict] = {}
	for c in charts:
		tank = c.tank or ""
		if tank and tank not in chart_map:
			chart_map[tank] = c

	rows = []
	for t in tanks:
		chart = chart_map.get(t.name)
		if not chart:
			rows.append(
				{
					"category": _("Missing Calibration"),
					"station": t.station,
					"issue": _("Tank {0} has no calibration chart").format(t.name),
					"document": t.name,
					"doctype": "Fuel Tank",
					"age_days": 0,
				}
			)
		elif chart.get("valid_to") and getdate(chart["valid_to"]) <= getdate(warn_date):
			days_left = (getdate(chart["valid_to"]) - today).days
			rows.append(
				{
					"category": _("Chart Expiring"),
					"station": t.station,
					"issue": _("Calibration chart for {0} expires in {1} days").format(t.name, days_left),
					"document": chart["name"],
					"doctype": "Tank Calibration Chart",
					"age_days": max(0, -days_left),
				}
			)
	return rows


def _active_stations(station_filter=None) -> list[str]:
	f = {}
	if station_filter:
		f["name"] = station_filter
	return frappe.get_all("Station", filters=f, pluck="name") if frappe.db.table_exists("Station") else []


def send_daily() -> None:
	"""Scheduled entry point — email FMS Health to admins and area managers."""
	rows = _data({})
	if not rows:
		return

	body = _build_email_body(rows)
	recipients = _get_recipients()
	if not recipients:
		return

	frappe.sendmail(
		recipients=recipients,
		subject=_("[FMS Health] {0} issues found — {1}").format(len(rows), nowdate()),
		message=body,
		delayed=False,
	)


def _build_email_body(rows: list[dict]) -> str:
	header = "<h3>{0}</h3>".format(_("FMS Health Report — {0}").format(nowdate()))
	table_rows = "".join(
		"<tr><td>{category}</td><td>{station}</td><td>{issue}</td><td>{age_days}</td></tr>".format_map(
			{k: (v or "") for k, v in row.items()}
		)
		for row in rows
	)
	table = (
		"<table border='1' cellpadding='4' cellspacing='0'>"
		"<thead><tr><th>{0}</th><th>{1}</th><th>{2}</th><th>{3}</th></tr></thead>"
		"<tbody>{4}</tbody></table>"
	).format(_("Category"), _("Station"), _("Issue"), _("Age (days)"), table_rows)
	return header + table


def _get_recipients() -> list[str]:
	roles = ["Forecourt Administrator", "Area Manager", "Forecourt Director"]
	users: set[str] = set()
	for role in roles:
		for u in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"):
			if u and u != "Administrator":
				users.add(u)
	admin_email = frappe.db.get_value("User", "Administrator", "email") or ""
	if admin_email:
		users.add(admin_email)
	return list(users)
