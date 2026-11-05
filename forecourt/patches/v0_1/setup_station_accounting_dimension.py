import frappe


def execute() -> None:
	"""Ensure the Station Accounting Dimension columns exist in all relevant DocTypes.

	Fixture import of Accounting Dimension records does not trigger on_update,
	so make_dimension_in_accounting_doctypes is never called.  Without this patch
	the `station` column is absent from tabStock Entry and others, causing SQL
	errors when shifts are closed.
	"""
	if not frappe.db.exists("Accounting Dimension", "Station"):
		return

	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
		make_dimension_in_accounting_doctypes,
	)

	doc = frappe.get_doc("Accounting Dimension", "Station")
	make_dimension_in_accounting_doctypes(doc=doc)
