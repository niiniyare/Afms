"""Cash Position by Station — FMS-H05.

Net GL balance of the station's till account(s) per station, as at a given date.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, today

from forecourt.reports.common import permitted_stations


def execute(filters=None):
	filters = filters or {}
	return _columns(), _data(filters)


def _columns():
	return [
		{
			"label": _("Station"),
			"fieldname": "station",
			"fieldtype": "Link",
			"options": "Station",
			"width": 140,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 130,
		},
		{
			"label": _("Till Account"),
			"fieldname": "account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 180,
		},
		{"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
	]


def _data(filters):
	as_of = filters.get("date") or today()

	# Collect till accounts from Station Till Account child table
	# Station DocType: permission enforced via name field (station IS the name)
	permitted = permitted_stations()
	if permitted is not None and not permitted:
		return []

	station_f = {}
	if filters.get("station"):
		if permitted is not None and filters["station"] not in permitted:
			return []
		station_f["name"] = filters["station"]
	elif permitted is not None:
		station_f["name"] = ["in", permitted]
	if filters.get("company"):
		station_f["company"] = filters["company"]

	stations = frappe.get_all("Station", filters=station_f, fields=["name", "company"])

	till_accounts: list[dict] = []
	for s in stations:
		tills = frappe.get_all(
			"Station Till Account",
			filters={"parent": s.name},
			fields=["account"],
		)
		for t in tills:
			if t.account:
				till_accounts.append({"station": s.name, "company": s.company, "account": t.account})

	if not till_accounts:
		return []

	GLE = frappe.qb.DocType("GL Entry")
	result = []
	for ta in till_accounts:
		gl_data = (
			frappe.qb.from_(GLE)
			.select(Sum(GLE.debit).as_("debit"), Sum(GLE.credit).as_("credit"))
			.where(GLE.account == ta["account"])
			.where(GLE.company == ta["company"])
			.where(GLE.station == ta["station"])
			.where(GLE.posting_date <= as_of)
			.where(GLE.is_cancelled == 0)
		).run(as_dict=True)
		debit = flt((gl_data[0].debit if gl_data else 0) or 0, 2)
		credit = flt((gl_data[0].credit if gl_data else 0) or 0, 2)
		result.append(
			{
				"station": ta["station"],
				"company": ta["company"],
				"account": ta["account"],
				"debit": debit,
				"credit": credit,
				"balance": flt(debit - credit, 2),
			}
		)

	return sorted(result, key=lambda r: (r["company"] or "", r["station"] or ""))
