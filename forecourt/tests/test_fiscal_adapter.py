"""Fiscal adapter tests — FMS-J07, FMS-J08.

Unit tests for the fiscal adapter interface and Kenya eTIMS adapter.
All HTTP calls are mocked; no network access required.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub frappe at module import time so pure-Python adapters can be loaded
# ---------------------------------------------------------------------------


def setUpModule() -> None:
	import frappe

	frappe.db = MagicMock()
	frappe.flags = SimpleNamespace(in_test=True)
	frappe.session = SimpleNamespace(user="test@example.com")
	frappe.get_cached_doc = MagicMock()
	frappe.log_error = MagicMock()
	frappe._ = lambda s, *a, **kw: s
	frappe.get_attr = _real_get_attr
	# Required by now_datetime() → get_system_timezone() → get_system_settings("time_zone")
	frappe.get_system_settings = MagicMock(
		side_effect=lambda key: {
			"time_zone": "Africa/Nairobi",
			"rounding_method": "Banker's Rounding (legacy)",
		}.get(key, "")
	)


def _real_get_attr(dotted: str) -> object:
	"""Import and return the class at the given dotted path."""
	parts = dotted.rsplit(".", 1)
	mod = __import__(parts[0], fromlist=[parts[1]])
	return getattr(mod, parts[1])


# ---------------------------------------------------------------------------
# FiscalResult
# ---------------------------------------------------------------------------


class TestFiscalResult(unittest.TestCase):
	def test_defaults(self) -> None:
		from forecourt.forecourt_integrations.fiscal_adapters import FiscalResult

		r = FiscalResult(success=True)
		self.assertTrue(r.success)
		self.assertEqual(r.receipt_no, "")
		self.assertEqual(r.raw, {})

	def test_failure(self) -> None:
		from forecourt.forecourt_integrations.fiscal_adapters import FiscalResult

		r = FiscalResult(success=False, error="timeout")
		self.assertFalse(r.success)
		self.assertEqual(r.error, "timeout")


# ---------------------------------------------------------------------------
# get_adapter registry
# ---------------------------------------------------------------------------


class TestGetAdapter(unittest.TestCase):
	def test_none_for_empty(self) -> None:
		from forecourt.forecourt_integrations.fiscal_adapters import get_adapter

		self.assertIsNone(get_adapter(""))

	def test_none_for_unknown(self) -> None:
		from forecourt.forecourt_integrations.fiscal_adapters import get_adapter

		self.assertIsNone(get_adapter("Unknown Adapter XYZ"))

	def test_etims_adapter_returned(self) -> None:
		from forecourt.forecourt_integrations.fiscal_adapters import (
			FiscalAdapter,
			get_adapter,
		)

		adapter = get_adapter("eTIMS Kenya")
		self.assertIsNotNone(adapter)
		self.assertIsInstance(adapter, FiscalAdapter)


# ---------------------------------------------------------------------------
# KenyaETIMSAdapter — mocked HTTP
# ---------------------------------------------------------------------------


class TestKenyaETIMSAdapterSubmit(unittest.TestCase):
	def _adapter(self):
		from forecourt.forecourt_integrations.fiscal_adapters.etims import (
			KenyaETIMSAdapter,
		)

		return KenyaETIMSAdapter()

	def _mock_settings(self) -> SimpleNamespace:
		return SimpleNamespace(
			fiscal_adapter="eTIMS Kenya",
			fiscal_sandbox_mode=1,
			fiscal_device_id="00",
			fiscal_device_serial="TEST123",
			fiscal_api_url="",
			get_password=MagicMock(return_value="test-api-key"),
		)

	def _mock_invoice(self) -> SimpleNamespace:
		item = SimpleNamespace(
			item_code="AGO",
			item_name="AGO",
			qty=150.0,
			rate=150.0,
			amount=22500.0,
			uom="Ltr",
			discount_percentage=0,
			discount_amount=0,
			net_amount=22500.0,
		)
		return SimpleNamespace(
			name="SINV-0001",
			company="Test Co",
			posting_date="2026-10-01",
			posting_time="14:00:00",
			customer_name="Walk-in",
			tax_id="",
			net_total=19396.55,
			total_taxes_and_charges=3103.45,
			grand_total=22500.0,
			remarks="",
			payments=[],
			items=[item],
			fms_fiscal_receipt_no="",
		)

	def test_submit_success(self) -> None:
		import frappe

		adapter = self._adapter()
		invoice = self._mock_invoice()
		settings = self._mock_settings()
		frappe.get_cached_doc.return_value = settings

		api_response = {
			"resultCd": "000",
			"resultMsg": "Success",
			"data": {
				"rcptSign": "RCPT-12345",
				"vsdcRcptPbctDt": "SIG-ABCDEF",
			},
		}

		with patch("requests.post") as mock_post:
			mock_post.return_value = MagicMock(
				status_code=200,
				json=MagicMock(return_value=api_response),
				raise_for_status=MagicMock(),
			)
			result = adapter.submit(invoice)

		self.assertTrue(result.success)
		self.assertEqual(result.receipt_no, "RCPT-12345")
		self.assertEqual(result.signature, "SIG-ABCDEF")
		self.assertTrue(result.qr_data.startswith("KRA:"))
		mock_post.assert_called_once()
		url = mock_post.call_args[0][0]
		self.assertIn("etims-sbx.kra.go.ke", url)  # sandbox
		self.assertIn("insertTrnsSalesOsdc", url)

	def test_submit_api_error(self) -> None:
		import frappe

		adapter = self._adapter()
		invoice = self._mock_invoice()
		settings = self._mock_settings()
		frappe.get_cached_doc.return_value = settings

		api_response = {"resultCd": "101", "resultMsg": "Unauthorized"}

		with patch("requests.post") as mock_post:
			mock_post.return_value = MagicMock(
				status_code=200,
				json=MagicMock(return_value=api_response),
				raise_for_status=MagicMock(),
			)
			result = adapter.submit(invoice)

		self.assertFalse(result.success)
		self.assertIn("Unauthorized", result.error)

	def test_cancel_success(self) -> None:
		import frappe

		adapter = self._adapter()
		invoice = self._mock_invoice()
		invoice.fms_fiscal_receipt_no = "RCPT-12345"
		settings = self._mock_settings()
		frappe.get_cached_doc.return_value = settings

		api_response = {"resultCd": "000", "resultMsg": "Cancelled"}

		with patch("requests.post") as mock_post:
			mock_post.return_value = MagicMock(
				status_code=200,
				json=MagicMock(return_value=api_response),
				raise_for_status=MagicMock(),
			)
			result = adapter.cancel(invoice)

		self.assertTrue(result.success)
		self.assertIn("insertTrnsSalesCancelOsdc", mock_post.call_args[0][0])

	def test_sandbox_vs_production_url(self) -> None:
		import frappe

		adapter = self._adapter()
		invoice = self._mock_invoice()

		# Production mode
		prod_settings = self._mock_settings()
		prod_settings.fiscal_sandbox_mode = 0
		frappe.get_cached_doc.return_value = prod_settings

		api_response = {"resultCd": "000", "data": {"rcptSign": "X"}}
		with patch("requests.post") as mock_post:
			mock_post.return_value = MagicMock(
				status_code=200,
				json=MagicMock(return_value=api_response),
				raise_for_status=MagicMock(),
			)
			adapter.submit(invoice)

		url = mock_post.call_args[0][0]
		self.assertIn("etims-api.kra.go.ke", url)
		self.assertNotIn("sbx", url)

	def test_payment_type_mapping(self) -> None:
		from forecourt.forecourt_integrations.fiscal_adapters.etims import (
			KenyaETIMSAdapter,
		)

		mpesa_invoice = SimpleNamespace(payments=[SimpleNamespace(mode_of_payment="Mobile Money (M-Pesa)")])
		card_invoice = SimpleNamespace(payments=[SimpleNamespace(mode_of_payment="Visa Card")])
		cash_invoice = SimpleNamespace(payments=[])

		self.assertEqual(KenyaETIMSAdapter._payment_type_code(mpesa_invoice), "04")
		self.assertEqual(KenyaETIMSAdapter._payment_type_code(card_invoice), "02")
		self.assertEqual(KenyaETIMSAdapter._payment_type_code(cash_invoice), "01")


# ---------------------------------------------------------------------------
# fiscal_hooks — _needs_fiscalisation, process_fiscal_submit
# ---------------------------------------------------------------------------


class TestFiscalHooks(unittest.TestCase):
	def test_needs_fiscalisation_false_when_no_adapter(self) -> None:
		import frappe

		from forecourt.forecourt_integrations.fiscal_hooks import _needs_fiscalisation

		frappe.get_cached_doc.return_value = SimpleNamespace(fiscal_adapter="")
		inv = SimpleNamespace(company="Test Co")
		self.assertFalse(_needs_fiscalisation(inv))

	def test_needs_fiscalisation_true_when_adapter_set(self) -> None:
		import frappe

		from forecourt.forecourt_integrations.fiscal_hooks import _needs_fiscalisation

		frappe.get_cached_doc.return_value = SimpleNamespace(fiscal_adapter="eTIMS Kenya")
		inv = SimpleNamespace(company="Test Co")
		self.assertTrue(_needs_fiscalisation(inv))

	def test_process_fiscal_submit_stores_receipt(self) -> None:
		from forecourt.forecourt_integrations.fiscal_adapters import FiscalResult
		from forecourt.forecourt_integrations.fiscal_hooks import process_fiscal_submit

		inbox = SimpleNamespace(payload=json.dumps({"invoice": "SINV-0001", "company": "Test Co"}))

		mock_result = FiscalResult(
			success=True,
			receipt_no="RCPT-99",
			signature="SIG-XX",
			qr_data="KRA:RCPT-99:abc",
		)

		mock_invoice = SimpleNamespace(company="Test Co", items=[])
		mock_db = MagicMock()

		with (
			patch("forecourt.forecourt_integrations.fiscal_hooks._get_adapter") as mock_get_adapter,
			patch("frappe.get_doc", return_value=mock_invoice),
			patch("frappe.db", mock_db),
		):
			mock_adapter = MagicMock()
			mock_adapter.submit.return_value = mock_result
			mock_get_adapter.return_value = mock_adapter

			ret = process_fiscal_submit(inbox)

			mock_db.set_value.assert_called_once()
			call_args = mock_db.set_value.call_args[0]
			self.assertEqual(call_args[1], "SINV-0001")
			self.assertEqual(call_args[2]["fms_fiscal_status"], "Submitted")
			self.assertEqual(call_args[2]["fms_fiscal_receipt_no"], "RCPT-99")

		self.assertEqual(ret, {"doctype": "Sales Invoice", "name": "SINV-0001"})


if __name__ == "__main__":
	unittest.main()
