"""M-Pesa C2B confirmation callback adapter — FMS-J05.

Endpoint (whitelisted, no auth gate — M-Pesa signs via shortcode):
    POST /api/method/forecourt.forecourt_integrations.payment_adapters.mpesa.c2b_callback

Expected payload (Safaricom C2B v2 format):
    {
      "TransactionType": "Pay Bill",
      "TransID": "QAA00000001",
      "TransTime": "20261101071200",
      "TransAmount": "1500.00",
      "BusinessShortCode": "123456",
      "BillRefNumber": "INV001",
      "InvoiceNumber": "",
      "OrgAccountBalance": "0",
      "ThirdPartyTransID": "",
      "MSISDN": "2547XXXXXXXX",
      "FirstName": "John",
      "LastName": "Doe"
    }

Configuration in site_config.json:
    "mpesa_c2b_shortcode": "123456",          # expected shortcode
    "mpesa_c2b_provider": "M-Pesa",           # Payment Provider name
    "mpesa_c2b_default_station": "STA-001"    # fallback station (till matching resolves the real one)

Returns Safaricom acknowledgment: {"ResultCode": 0, "ResultDesc": "Accepted"}
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime


@frappe.whitelist(allow_guest=True, methods=["POST"])
def c2b_callback(**kwargs) -> dict:
	"""Receive M-Pesa C2B confirmation and create Integration Inbox row."""
	try:
		payload = _parse_payload()
		trans_id = payload.get("TransID") or ""
		if not trans_id:
			return {"ResultCode": 1, "ResultDesc": "Missing TransID"}

		provider = frappe.conf.get("mpesa_c2b_provider") or "M-Pesa"
		shortcode = str(frappe.conf.get("mpesa_c2b_shortcode") or "")
		incoming_shortcode = str(payload.get("BusinessShortCode") or "")

		if shortcode and incoming_shortcode and incoming_shortcode != shortcode:
			frappe.logger("mpesa").warning(
				f"M-Pesa callback shortcode mismatch: expected {shortcode}, got {incoming_shortcode}"
			)
			return {"ResultCode": 1, "ResultDesc": "Invalid ShortCode"}

		# Idempotent: skip if already in inbox
		existing = frappe.db.get_value(
			"Integration Inbox",
			{"provider": provider, "external_id": trans_id},
			"name",
		)
		if existing:
			return {"ResultCode": 0, "ResultDesc": "Accepted"}

		inbox = frappe.get_doc(
			{
				"doctype": "Integration Inbox",
				"provider": provider,
				"direction": "In",
				"message_type": "c2b_confirmation",
				"external_id": trans_id,
				"payload": json.dumps(payload),
				"status": "Received",
				"received_at": now_datetime(),
			}
		)
		inbox.flags.ignore_permissions = True
		inbox.insert()

		return {"ResultCode": 0, "ResultDesc": "Accepted"}

	except Exception:
		frappe.log_error(frappe.get_traceback(), "M-Pesa c2b_callback error")
		return {"ResultCode": 1, "ResultDesc": "Internal error"}


def _parse_payload() -> dict:
	"""Extract payload from POST body or form data."""
	try:
		body = frappe.request.get_data(as_text=True)
		if body:
			return json.loads(body)
	except (ValueError, AttributeError):
		pass
	return frappe.form_dict or {}


# ---------------------------------------------------------------------------
# Inbox processor handler — registered in inbox_processor._HANDLERS
# ---------------------------------------------------------------------------


def handle_c2b_confirmation(inbox: "frappe.Document") -> dict | None:
	"""Create a Payment Feed Entry from a c2b_confirmation inbox row."""
	payload = json.loads(inbox.payload) if isinstance(inbox.payload, str) else inbox.payload
	if not payload:
		frappe.throw(_("Empty payload in inbox row {0}").format(inbox.name))

	trans_id = payload.get("TransID") or ""
	amount_str = payload.get("TransAmount") or "0"
	trans_time_str = payload.get("TransTime") or ""
	msisdn = payload.get("MSISDN") or ""
	first = payload.get("FirstName") or ""
	last = payload.get("LastName") or ""
	payer = f"{first} {last}".strip() or msisdn
	till = str(payload.get("BusinessShortCode") or "")

	provider = inbox.provider
	station = _resolve_station(provider, till)
	trans_time = _parse_mpesa_time(trans_time_str)

	existing = frappe.db.get_value(
		"Payment Feed Entry",
		{"provider": provider, "reference": trans_id},
		"name",
	)
	if existing:
		return {"doctype": "Payment Feed Entry", "name": existing}

	feed = frappe.get_doc(
		{
			"doctype": "Payment Feed Entry",
			"provider": provider,
			"station": station,
			"till_or_terminal": till,
			"reference": trans_id,
			"transaction_time": trans_time,
			"amount": float(amount_str),
			"payer": payer,
			"status": "Unmatched",
			"inbox": inbox.name,
		}
	)
	feed.flags.ignore_permissions = True
	feed.insert()
	return {"doctype": "Payment Feed Entry", "name": feed.name}


def _resolve_station(provider: str, till: str) -> str:
	"""Resolve station from till_to_cashier mapping on the provider."""
	from forecourt.forecourt_integrations.statement_import import _load_mapping

	provider_doc = frappe.get_cached_doc("Payment Provider", provider)
	mapping = _load_mapping(provider_doc)
	till_station_map: dict[str, str] = mapping.get("till_to_station") or {}
	station = till_station_map.get(till) or ""
	if not station:
		station = frappe.conf.get("mpesa_c2b_default_station") or ""
	return station


def _parse_mpesa_time(time_str: str) -> str:
	"""Parse M-Pesa TransTime format (YYYYMMDDHHmmss) to Frappe datetime."""
	if not time_str or len(time_str) < 14:
		return str(now_datetime())
	try:
		from datetime import datetime

		dt = datetime.strptime(time_str[:14], "%Y%m%d%H%M%S")
		return str(dt)
	except ValueError:
		return str(now_datetime())
