"""Kenya eTIMS fiscal adapter — FMS-J07.

Implements the KRA eTIMS Lite API (VSCU / Online SDCS).
Reference: KRA eTIMS Lite API Integration Guide v2.x.

Configuration (on Forecourt Company Settings):
  fiscal_sandbox_mode   Check  → uses sandbox base URL
  fiscal_device_id      Data   → BHF ID (Branch Head File ID), e.g. "00"
  fiscal_api_url        Data   → override base URL (optional)
  fiscal_device_serial  Data   → device serial number

Credentials stored in ERPNext Password field (fiscal_api_key) so they
never appear in fixtures or logs.

Sandbox base URL: https://etims-sbx.kra.go.ke/etims-api
Production URL  : https://etims-api.kra.go.ke/etims-api

The adapter:
1. Builds a sale transaction payload from the Sales Invoice.
2. POSTs to /api/fns/{bhf_id}/insertTrnsSalesOsdc.
3. On HTTP 200 with result_cd "000": stores receipt number + QR on the invoice.
4. On any error: raises to let the Integration Inbox mark the row Failed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from forecourt.forecourt_integrations.fiscal_adapters import FiscalResult

_SANDBOX_URL = "https://etims-sbx.kra.go.ke/etims-api"
_PROD_URL = "https://etims-api.kra.go.ke/etims-api"
_TIMEOUT = 30


class KenyaETIMSAdapter:
	"""Kenya eTIMS Lite (VSCU / OSDC) fiscal adapter."""

	# ------------------------------------------------------------------
	# Public interface
	# ------------------------------------------------------------------

	def submit(self, invoice: frappe.Document) -> FiscalResult:
		settings = self._company_settings(invoice.company)
		base_url = self._base_url(settings)
		bhf_id = settings.fiscal_device_id or "00"
		api_key = settings.get_password("fiscal_api_key") or ""

		payload = self._build_submit_payload(invoice, bhf_id)
		url = f"{base_url}/api/fns/{bhf_id}/insertTrnsSalesOsdc"
		resp = self._post(url, payload, api_key)

		if resp.get("resultCd") == "000":
			data = resp.get("data") or {}
			receipt_no = str(data.get("rcptSign") or data.get("intrlData") or "")
			signature = str(data.get("vsdcRcptPbctDt") or data.get("rcptSign") or "")
			qr_data = self._build_qr(receipt_no, signature, invoice)
			return FiscalResult(
				success=True,
				receipt_no=receipt_no,
				signature=signature,
				qr_data=qr_data,
				raw=resp,
			)

		err = resp.get("resultMsg") or json.dumps(resp)
		return FiscalResult(success=False, error=err, raw=resp)

	def status(self, invoice: frappe.Document) -> FiscalResult:
		settings = self._company_settings(invoice.company)
		base_url = self._base_url(settings)
		bhf_id = settings.fiscal_device_id or "00"
		api_key = settings.get_password("fiscal_api_key") or ""

		url = f"{base_url}/api/fns/{bhf_id}/selectTrnsSalesOsdc"
		payload = {"bhfId": bhf_id, "lastReqDt": "20200101000000"}
		resp = self._post(url, payload, api_key)

		return FiscalResult(
			success=resp.get("resultCd") == "000",
			receipt_no=invoice.fms_fiscal_receipt_no or "",
			error=resp.get("resultMsg") or "",
			raw=resp,
		)

	def cancel(self, invoice: frappe.Document) -> FiscalResult:
		settings = self._company_settings(invoice.company)
		base_url = self._base_url(settings)
		bhf_id = settings.fiscal_device_id or "00"
		api_key = settings.get_password("fiscal_api_key") or ""

		payload = self._build_cancel_payload(invoice, bhf_id)
		url = f"{base_url}/api/fns/{bhf_id}/insertTrnsSalesCancelOsdc"
		resp = self._post(url, payload, api_key)

		success = resp.get("resultCd") == "000"
		return FiscalResult(
			success=success,
			error="" if success else (resp.get("resultMsg") or json.dumps(resp)),
			raw=resp,
		)

	# ------------------------------------------------------------------
	# Payload builders
	# ------------------------------------------------------------------

	def _build_submit_payload(self, invoice: frappe.Document, bhf_id: str) -> dict:
		now = now_datetime()
		sale_date = self._fmt_dt(invoice.posting_date, invoice.posting_time or "00:00:00")
		items = []
		for idx, row in enumerate(invoice.items or [], 1):
			items.append(
				{
					"itemSeq": idx,
					"itemCd": row.item_code or "",
					"itemClsCd": "5020230602",  # petroleum products (HS 5020230602)
					"itemNm": row.item_name or row.item_code or "",
					"bcd": row.item_code or "",
					"pkgUnitCd": "L" if row.uom in ("Ltr", "L", "Litre") else "U",
					"pkg": flt(row.qty, 3),
					"qtyUnitCd": row.uom or "U",
					"qty": flt(row.qty, 3),
					"prc": flt(row.rate, 2),
					"splyAmt": flt(row.amount, 2),
					"dcRt": flt(row.discount_percentage or 0, 2),
					"dcAmt": flt(row.discount_amount or 0, 2),
					"taxblAmt": flt(row.net_amount or row.amount, 2),
					"taxTyCd": "B",  # standard VAT
					"taxAmt": flt((row.net_amount or row.amount) * 0.16, 2),  # 16 % Kenya VAT
					"totAmt": flt(row.amount, 2),
				}
			)

		return {
			"bhfId": bhf_id,
			"invcNo": invoice.name,
			"orgInvcNo": "",
			"salesTyCd": "N",  # Normal sale
			"rcptTyCd": "S",  # Simplified tax invoice
			"pmtTyCd": self._payment_type_code(invoice),
			"salesSttsCd": "02",  # Approved
			"cfmDt": self._fmt_dt(now.date(), now.strftime("%H:%M:%S")),
			"salesDt": sale_date,
			"stockRlsDt": sale_date,
			"cnclReqDt": None,
			"cnclDt": None,
			"rfdDt": None,
			"rfdRsnCd": None,
			"totItemCnt": len(items),
			"taxblAmtA": 0,
			"taxblAmtB": flt(invoice.net_total, 2),
			"taxblAmtC": 0,
			"taxblAmtD": 0,
			"taxRtA": 0,
			"taxRtB": 16,
			"taxRtC": 0,
			"taxRtD": 0,
			"taxAmtA": 0,
			"taxAmtB": flt(invoice.total_taxes_and_charges or 0, 2),
			"taxAmtC": 0,
			"taxAmtD": 0,
			"totTaxblAmt": flt(invoice.net_total, 2),
			"totTaxAmt": flt(invoice.total_taxes_and_charges or 0, 2),
			"totAmt": flt(invoice.grand_total, 2),
			"prchrAcptcYn": "N",
			"remark": invoice.remarks or "",
			"regrId": frappe.session.user or "Administrator",
			"regrNm": frappe.session.user or "Administrator",
			"modrId": frappe.session.user or "Administrator",
			"modrNm": frappe.session.user or "Administrator",
			"receipt": {
				"custTin": (invoice.tax_id or "").replace("-", "") or "0000000000",
				"custMblNo": "",
				"rptNo": 0,
				"trdeNm": invoice.customer_name or "",
				"adrs": "",
				"topMsg": "THANK YOU FOR YOUR BUSINESS",
				"btmMsg": "",
				"prchrAcptcYn": "N",
			},
			"itemList": items,
		}

	def _build_cancel_payload(self, invoice: frappe.Document, bhf_id: str) -> dict:
		now = now_datetime()
		return {
			"bhfId": bhf_id,
			"orgInvcNo": invoice.name,
			"invcNo": f"{invoice.name}-CANCEL",
			"salesTyCd": "C",  # Cancel
			"rcptTyCd": "S",
			"cnclReqDt": self._fmt_dt(now.date(), now.strftime("%H:%M:%S")),
			"cnclDt": self._fmt_dt(now.date(), now.strftime("%H:%M:%S")),
			"rfdRsnCd": "05",
			"totItemCnt": 0,
			"taxblAmtA": 0,
			"taxblAmtB": 0,
			"taxblAmtC": 0,
			"taxblAmtD": 0,
			"taxAmtA": 0,
			"taxAmtB": 0,
			"taxAmtC": 0,
			"taxAmtD": 0,
			"totTaxblAmt": 0,
			"totTaxAmt": 0,
			"totAmt": 0,
			"remark": _("Cancelled"),
			"regrId": frappe.session.user or "Administrator",
			"regrNm": frappe.session.user or "Administrator",
			"modrId": frappe.session.user or "Administrator",
			"modrNm": frappe.session.user or "Administrator",
			"itemList": [],
		}

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	@staticmethod
	def _company_settings(company: str) -> frappe.Document:
		return frappe.get_cached_doc("Forecourt Company Settings", company)

	@staticmethod
	def _base_url(settings: frappe.Document) -> str:
		if settings.fiscal_api_url:
			return settings.fiscal_api_url.rstrip("/")
		return _SANDBOX_URL if settings.fiscal_sandbox_mode else _PROD_URL

	@staticmethod
	def _fmt_dt(date: object, time: object) -> str:
		"""Format a date + time as eTIMS YYYYMMDDHHmmss string."""
		d = str(date).replace("-", "")
		t = str(time).replace(":", "")[:6]
		return d + t.ljust(6, "0")

	@staticmethod
	def _payment_type_code(invoice: frappe.Document) -> str:
		"""Map the invoice's payment method to eTIMS payment type code."""
		modes = [m.mode_of_payment for m in (invoice.payments or [])]
		if not modes:
			return "01"  # Cash
		first = modes[0].lower()
		if "mobile" in first or "mpesa" in first or "momo" in first:
			return "04"  # Mobile money
		if "card" in first or "visa" in first or "mastercard" in first:
			return "02"  # Credit/debit card
		if "credit" in first or "account" in first:
			return "05"  # Credit
		return "01"

	@staticmethod
	def _build_qr(receipt_no: str, signature: str, invoice: frappe.Document) -> str:
		"""Build a minimal QR payload; a real QR image is rendered in the print format."""
		h = hashlib.sha256(f"{invoice.name}|{receipt_no}|{invoice.grand_total}".encode()).hexdigest()[:16]
		return f"KRA:{receipt_no}:{h}"

	@staticmethod
	def _post(url: str, payload: dict, api_key: str) -> dict:
		import requests

		headers = {
			"Content-Type": "application/json",
		}
		if api_key:
			headers["Authorization"] = api_key

		try:
			resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
			resp.raise_for_status()
			return resp.json()
		except requests.exceptions.RequestException as exc:
			frappe.log_error(str(exc), "eTIMS API Error")
			raise
