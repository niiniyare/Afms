"""Fiscal integration hooks — FMS-J07.

doc_events handler: Sales Invoice on_submit.

Creates an outbound Integration Inbox row so the fiscal adapter call runs in
the background and does not block the web request.  Synchronous mode is used
in tests (frappe.flags.in_test).
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime


def on_submit_sales_invoice(doc: frappe.Document, method: str | None = None) -> None:
	"""Enqueue fiscal submission for a Sales Invoice if the company uses a fiscal adapter."""
	if not _needs_fiscalisation(doc):
		return

	inbox = frappe.get_doc(
		{
			"doctype": "Integration Inbox",
			"provider": doc.company,
			"direction": "Out",
			"message_type": "fiscal_submit",
			"status": "Received",
			"external_id": doc.name,
			"received_at": now_datetime(),
			"payload": json.dumps({"invoice": doc.name, "company": doc.company}),
		}
	)
	inbox.insert(ignore_permissions=True)

	frappe.enqueue(
		"forecourt.forecourt_integrations.inbox_processor.process",
		inbox_name=inbox.name,
		queue="default",
		timeout=60,
		now=frappe.flags.in_test,
		enqueue_after_commit=True,
	)


def on_cancel_sales_invoice(doc: frappe.Document, method: str | None = None) -> None:
	"""Enqueue fiscal cancellation if the invoice was previously fiscalised."""
	if not doc.get("fms_fiscal_receipt_no"):
		return
	if not _needs_fiscalisation(doc):
		return

	inbox = frappe.get_doc(
		{
			"doctype": "Integration Inbox",
			"provider": doc.company,
			"direction": "Out",
			"message_type": "fiscal_cancel",
			"status": "Received",
			"external_id": doc.name,
			"received_at": now_datetime(),
			"payload": json.dumps({"invoice": doc.name, "company": doc.company}),
		}
	)
	inbox.insert(ignore_permissions=True)

	frappe.enqueue(
		"forecourt.forecourt_integrations.inbox_processor.process",
		inbox_name=inbox.name,
		queue="default",
		timeout=60,
		now=frappe.flags.in_test,
		enqueue_after_commit=True,
	)


def process_fiscal_submit(inbox: frappe.Document) -> dict | None:
	"""Inbox processor handler for fiscal_submit messages."""
	data = json.loads(inbox.payload or "{}")
	invoice_name = data.get("invoice")
	company = data.get("company")

	if not invoice_name or not company:
		return None

	adapter = _get_adapter(company)
	if not adapter:
		return None

	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	result = adapter.submit(invoice)

	if result.success:
		frappe.db.set_value(
			"Sales Invoice",
			invoice_name,
			{
				"fms_fiscal_status": "Submitted",
				"fms_fiscal_receipt_no": result.receipt_no,
				"fms_fiscal_signature": result.signature,
				"fms_fiscal_qr": result.qr_data,
			},
		)
	else:
		frappe.db.set_value(
			"Sales Invoice",
			invoice_name,
			{"fms_fiscal_status": "Failed"},
		)
		frappe.throw(_("eTIMS submission failed for {0}: {1}").format(invoice_name, result.error))

	return {"doctype": "Sales Invoice", "name": invoice_name}


def process_fiscal_cancel(inbox: frappe.Document) -> dict | None:
	"""Inbox processor handler for fiscal_cancel messages."""
	data = json.loads(inbox.payload or "{}")
	invoice_name = data.get("invoice")
	company = data.get("company")

	if not invoice_name or not company:
		return None

	adapter = _get_adapter(company)
	if not adapter:
		return None

	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	result = adapter.cancel(invoice)

	if result.success:
		frappe.db.set_value("Sales Invoice", invoice_name, {"fms_fiscal_status": "Cancelled"})
	else:
		frappe.throw(_("eTIMS cancel failed for {0}: {1}").format(invoice_name, result.error))

	return {"doctype": "Sales Invoice", "name": invoice_name}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _needs_fiscalisation(doc: frappe.Document) -> bool:
	"""Return True if the company has a fiscal adapter configured."""
	try:
		settings = frappe.get_cached_doc("Forecourt Company Settings", doc.company)
		return bool(settings.fiscal_adapter)
	except Exception:
		return False


def _get_adapter(company: str) -> object | None:
	from forecourt.forecourt_integrations.fiscal_adapters import get_adapter

	try:
		settings = frappe.get_cached_doc("Forecourt Company Settings", company)
		return get_adapter(settings.fiscal_adapter or "")
	except Exception:
		return None
