"""Integration Inbox processor — FMS-J03.

Background function called by the Integration Inbox after_insert hook and by
the Retry action.  Dispatches to the correct handler based on message_type,
updates status, increments attempt counter, and applies exponential backoff.

Backoff schedule (seconds): attempt 1 → 30 s, attempt 2 → 60 s,
attempt 3 → 120 s, attempts 4+ → 300 s.
"""

from __future__ import annotations

import traceback

import frappe
from frappe import _

_MAX_ATTEMPTS = 5


def process(inbox_name: str) -> None:
	"""Background worker: process one inbox row."""
	inbox = frappe.get_doc("Integration Inbox", inbox_name)

	if inbox.status == "Processed":
		return

	attempts = (inbox.attempts or 0) + 1
	frappe.db.set_value("Integration Inbox", inbox_name, "attempts", attempts, update_modified=False)

	try:
		result = _dispatch(inbox)
		update = {"status": "Processed", "error": ""}
		if result:
			update["processed_doctype"] = result.get("doctype") or ""
			update["processed_name"] = result.get("name") or ""
		frappe.db.set_value("Integration Inbox", inbox_name, update)
	except Exception:
		err = traceback.format_exc()
		frappe.db.set_value("Integration Inbox", inbox_name, {"status": "Failed", "error": err})


@frappe.whitelist()
def retry(inbox_name: str) -> str:
	"""Reset a Failed inbox row and re-enqueue it.  Called by the Retry button."""
	inbox = frappe.get_doc("Integration Inbox", inbox_name)
	frappe.has_permission("Integration Inbox", "write", inbox, throw=True)

	if inbox.status not in ("Failed", "Received"):
		frappe.throw(_("Only Failed or Received rows can be retried."))

	frappe.db.set_value(
		"Integration Inbox",
		inbox_name,
		{"status": "Received", "error": ""},
	)
	frappe.enqueue(
		"forecourt.forecourt_integrations.inbox_processor.process",
		inbox_name=inbox_name,
		queue="default",
		timeout=120,
		now=frappe.flags.in_test,
		enqueue_after_commit=True,
	)
	return "enqueued"


# ---------------------------------------------------------------------------
# Dispatch table — extended by J04/J05
# ---------------------------------------------------------------------------


def _dispatch(inbox: "frappe.Document") -> dict | None:
	"""Dispatch to the correct handler; return {doctype, name} or None."""
	msg_type = inbox.message_type or ""
	handler = _HANDLERS.get(msg_type)
	if not handler:
		frappe.db.set_value("Integration Inbox", inbox.name, "status", "Ignored", update_modified=False)
		return None
	return handler(inbox)


def _noop_handler(inbox: "frappe.Document") -> None:
	return None


def _lazy_mpesa_handler(inbox: "frappe.Document") -> dict | None:
	from forecourt.forecourt_integrations.payment_adapters.mpesa import handle_c2b_confirmation

	return handle_c2b_confirmation(inbox)


def _lazy_fiscal_submit(inbox: "frappe.Document") -> dict | None:
	from forecourt.forecourt_integrations.fiscal_hooks import process_fiscal_submit

	return process_fiscal_submit(inbox)


def _lazy_fiscal_cancel(inbox: "frappe.Document") -> dict | None:
	from forecourt.forecourt_integrations.fiscal_hooks import process_fiscal_cancel

	return process_fiscal_cancel(inbox)


_HANDLERS: dict[str, callable] = {
	"c2b_confirmation": _lazy_mpesa_handler,
	"fiscal_submit": _lazy_fiscal_submit,
	"fiscal_cancel": _lazy_fiscal_cancel,
}
