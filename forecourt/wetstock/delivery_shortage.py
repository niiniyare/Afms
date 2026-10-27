"""Whitelisted method: record delivery shortage as a draft Stock Entry (E04)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def create_shortage_entry(purchase_receipt: str, tank: str) -> str:
	"""Create a draft Material Issue Stock Entry for the delivery shortage.

	Returns the name of the new Stock Entry.
	"""
	pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
	if pr.docstatus != 1:
		frappe.throw(_("Purchase Receipt must be submitted first."))

	dip_row = None
	for row in pr.get("fms_delivery_dips", []):
		if row.tank == tank:
			dip_row = row
			break

	if not dip_row:
		frappe.throw(_("No delivery dip row found for tank {0} on GRN {1}.").format(tank, purchase_receipt))

	shortage_l = flt(dip_row.invoiced_l) - flt(dip_row.received_l)
	if shortage_l <= 0:
		frappe.throw(_("No shortage to record: received ≥ invoiced for tank {0}.").format(tank))

	if dip_row.shortage_stock_entry:
		frappe.throw(
			_("Shortage Stock Entry {0} already created for this dip row.").format(
				dip_row.shortage_stock_entry
			)
		)

	tank_doc = frappe.get_doc("Fuel Tank", tank)
	station = tank_doc.station
	company = frappe.db.get_value("Station", station, "company")

	claims_account = frappe.db.get_value(
		"Forecourt Company Settings",
		{"company": company},
		"delivery_shortage_claims_account",
	)

	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": company,
			"posting_date": frappe.utils.today(),
			"posting_time": frappe.utils.nowtime(),
			"fms_purchase_receipt": purchase_receipt,
			"remarks": _("Delivery shortage for GRN {0}, tank {1}").format(purchase_receipt, tank),
			"items": [
				{
					"item_code": tank_doc.item,
					"qty": shortage_l,
					"s_warehouse": tank_doc.warehouse,
					"expense_account": claims_account,
				}
			],
		}
	)

	se.flags.ignore_permissions = True
	se.insert()

	frappe.db.set_value(
		"GRN Delivery Dip",
		dip_row.name,
		"shortage_stock_entry",
		se.name,
	)

	return se.name
