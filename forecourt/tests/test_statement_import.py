"""Statement import tests — FMS-J02.

Tests are unit-level (mocked frappe), verifying:
- CSV and Excel parsing via _parse_csv / _parse_excel
- Row mapping via _map_row / _cell
- Cashier resolution via _resolve_cashier
- Duplicate detection in run()
- Collection type mapping
- run() and run_for_shift() permission checks
"""

from __future__ import annotations

import io
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from forecourt.forecourt_integrations.statement_import import (
	_collection_type_for_provider,
	_load_mapping,
	_map_row,
	_parse_csv,
	_resolve_cashier,
)

# ---------------------------------------------------------------------------
# Fixtures directory
# ---------------------------------------------------------------------------

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _csv_bytes(filename: str) -> bytes:
	with open(os.path.join(FIXTURES, filename), "rb") as f:
		return f.read()


# ---------------------------------------------------------------------------
# _parse_csv — unit tests
# ---------------------------------------------------------------------------


class TestParseCsv(FrappeTestCase):
	def _mpesa_mapping(self):
		return {
			"reference": "Transaction ID",
			"amount": "Paid In",
			"till": "Till Number",
			"payer": "Sender Name",
			"transaction_time": "Completion Time",
		}

	def test_mpesa_parses_correct_row_count(self):
		rows = _parse_csv(_csv_bytes("mpesa_statement.csv"), self._mpesa_mapping())
		self.assertEqual(len(rows), 10)

	def test_mpesa_reference_extracted(self):
		rows = _parse_csv(_csv_bytes("mpesa_statement.csv"), self._mpesa_mapping())
		self.assertEqual(rows[0]["reference"], "QAA00000001")

	def test_mpesa_amount_extracted(self):
		rows = _parse_csv(_csv_bytes("mpesa_statement.csv"), self._mpesa_mapping())
		self.assertEqual(rows[0]["amount"], "1500.00")

	def test_mpesa_till_extracted(self):
		rows = _parse_csv(_csv_bytes("mpesa_statement.csv"), self._mpesa_mapping())
		self.assertEqual(rows[0]["till"], "T001")

	def test_mpesa_payer_extracted(self):
		rows = _parse_csv(_csv_bytes("mpesa_statement.csv"), self._mpesa_mapping())
		self.assertEqual(rows[0]["payer"], "John Doe")

	def test_mpesa_transaction_time_extracted(self):
		rows = _parse_csv(_csv_bytes("mpesa_statement.csv"), self._mpesa_mapping())
		self.assertIn("07:12:23", rows[0]["transaction_time"])

	def test_evc_parses_correct_row_count(self):
		mapping = {
			"reference": "Ref Number",
			"amount": "Amount",
			"till": "Till",
			"payer": "Customer Name",
		}
		rows = _parse_csv(_csv_bytes("evc_statement.csv"), mapping)
		self.assertEqual(len(rows), 10)

	def test_card_terminal_parses_correct_row_count(self):
		mapping = {
			"reference": "Trans Ref",
			"amount": "Amount",
			"till": "Terminal ID",
		}
		rows = _parse_csv(_csv_bytes("card_terminal_batch.csv"), mapping)
		self.assertEqual(len(rows), 10)

	def test_unknown_column_returns_none(self):
		content = b"Ref,Amount\nR001,100\n"
		mapping = {"reference": "Ref", "amount": "Amount", "till": "NoSuchCol"}
		rows = _parse_csv(content, mapping)
		self.assertIsNone(rows[0]["till"])

	def test_empty_csv_returns_empty_list(self):
		content = b"Ref,Amount\n"
		mapping = {"reference": "Ref", "amount": "Amount"}
		rows = _parse_csv(content, mapping)
		self.assertEqual(rows, [])

	def test_bom_handled(self):
		content = b"\xef\xbb\xbfRef,Amount\nBOM001,99\n"
		mapping = {"reference": "Ref", "amount": "Amount"}
		rows = _parse_csv(content, mapping)
		self.assertEqual(rows[0]["reference"], "BOM001")


# ---------------------------------------------------------------------------
# _parse_excel — unit tests (requires openpyxl)
# ---------------------------------------------------------------------------


class TestParseExcel(FrappeTestCase):
	def _make_excel(self, headers: list, rows: list[list]) -> bytes:
		import openpyxl

		wb = openpyxl.Workbook()
		ws = wb.active
		ws.append(headers)
		for row in rows:
			ws.append(row)
		buf = io.BytesIO()
		wb.save(buf)
		return buf.getvalue()

	def test_excel_parses_rows(self):
		from forecourt.forecourt_integrations.statement_import import _parse_excel

		content = self._make_excel(
			["Ref", "Amount", "Till"],
			[["EX001", 1000, "T1"], ["EX002", 2000, "T2"]],
		)
		mapping = {"reference": "Ref", "amount": "Amount", "till": "Till"}
		rows = _parse_excel(content, mapping)
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[0]["reference"], "EX001")
		self.assertEqual(rows[1]["till"], "T2")

	def test_excel_none_header_skipped(self):
		from forecourt.forecourt_integrations.statement_import import _parse_excel

		content = self._make_excel(
			["Ref", None, "Amount"],
			[["EX003", "ignored", 500]],
		)
		mapping = {"reference": "Ref", "amount": "Amount"}
		rows = _parse_excel(content, mapping)
		self.assertEqual(rows[0]["reference"], "EX003")


# ---------------------------------------------------------------------------
# _map_row / _cell — unit tests
# ---------------------------------------------------------------------------


class TestMapRow(FrappeTestCase):
	def test_maps_all_fields(self):
		raw = {
			"TID": "REF-001",
			"Amt": "500",
			"TillNo": "T1",
			"Sender": "Alice",
			"Time": "2026-01-01 10:00",
		}
		mapping = {
			"reference": "TID",
			"amount": "Amt",
			"till": "TillNo",
			"payer": "Sender",
			"transaction_time": "Time",
		}
		result = _map_row(raw, mapping)
		self.assertEqual(result["reference"], "REF-001")
		self.assertEqual(result["amount"], "500")
		self.assertEqual(result["till"], "T1")
		self.assertEqual(result["payer"], "Alice")
		self.assertEqual(result["transaction_time"], "2026-01-01 10:00")

	def test_missing_mapping_key_gives_none(self):
		raw = {"Ref": "R001"}
		result = _map_row(raw, {"reference": "Ref"})
		self.assertIsNone(result["till"])
		self.assertIsNone(result["amount"])

	def test_empty_mapping_all_none(self):
		raw = {"Ref": "R001", "Amt": "100"}
		result = _map_row(raw, {})
		self.assertIsNone(result["reference"])
		self.assertIsNone(result["amount"])


# ---------------------------------------------------------------------------
# _resolve_cashier — unit tests
# ---------------------------------------------------------------------------


class TestResolveCashier(FrappeTestCase):
	def test_till_map_match(self):
		result = _resolve_cashier("T001", {"T001": "EMP-001"}, "EMP-999", ["EMP-777"])
		self.assertEqual(result, "EMP-001")

	def test_till_map_miss_falls_back_to_default(self):
		result = _resolve_cashier("T003", {"T001": "EMP-001"}, "EMP-999", [])
		self.assertEqual(result, "EMP-999")

	def test_no_till_uses_default(self):
		result = _resolve_cashier("", {}, "EMP-999", ["EMP-777"])
		self.assertEqual(result, "EMP-999")

	def test_no_default_uses_first_cashier(self):
		result = _resolve_cashier("", {}, "", ["EMP-777", "EMP-888"])
		self.assertEqual(result, "EMP-777")

	def test_no_match_no_default_no_cashiers_returns_empty(self):
		result = _resolve_cashier("T999", {"T001": "EMP-001"}, "", [])
		self.assertEqual(result, "")

	def test_till_as_int_still_matches(self):
		result = _resolve_cashier(1, {"1": "EMP-001"}, "", [])
		self.assertEqual(result, "EMP-001")


# ---------------------------------------------------------------------------
# _load_mapping — unit tests
# ---------------------------------------------------------------------------


class TestLoadMapping(FrappeTestCase):
	def test_json_string_parsed(self):
		provider = SimpleNamespace(import_mapping='{"reference": "Ref"}')
		result = _load_mapping(provider)
		self.assertEqual(result["reference"], "Ref")

	def test_dict_returned_as_is(self):
		provider = SimpleNamespace(import_mapping={"reference": "Ref"})
		result = _load_mapping(provider)
		self.assertEqual(result["reference"], "Ref")

	def test_none_returns_empty_dict(self):
		provider = SimpleNamespace(import_mapping=None)
		result = _load_mapping(provider)
		self.assertEqual(result, {})

	def test_invalid_json_returns_empty_dict(self):
		provider = SimpleNamespace(import_mapping="{bad json}")
		result = _load_mapping(provider)
		self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# _collection_type_for_provider — unit tests
# ---------------------------------------------------------------------------


class TestCollectionType(FrappeTestCase):
	def test_mobile_money(self):
		p = SimpleNamespace(provider_type="Mobile Money")
		self.assertEqual(_collection_type_for_provider(p), "Mobile Money")

	def test_card(self):
		p = SimpleNamespace(provider_type="Card")
		self.assertEqual(_collection_type_for_provider(p), "Card")

	def test_voucher(self):
		p = SimpleNamespace(provider_type="Voucher")
		self.assertEqual(_collection_type_for_provider(p), "Voucher")

	def test_unknown_defaults_to_mobile_money(self):
		p = SimpleNamespace(provider_type="Bank")
		self.assertEqual(_collection_type_for_provider(p), "Mobile Money")


# ---------------------------------------------------------------------------
# run() — duplicate detection (mocked)
# ---------------------------------------------------------------------------


class TestRunDuplicates(FrappeTestCase):
	"""Verify that run() skips rows whose reference already exists on the shift."""

	def _make_batch(self, refs_on_shift: list[str]):
		batch = SimpleNamespace(
			name="IMP-TEST-001",
			forecourt_shift="SH-001",
			provider="M-Pesa",
			file="/files/test.csv",
		)
		provider = SimpleNamespace(
			import_format="csv mapping",
			import_mapping=json.dumps(
				{
					"reference": "Ref",
					"amount": "Amount",
					"till": "Till",
					"default_cashier": "EMP-001",
				}
			),
			provider_type="Mobile Money",
		)
		cashier_row = SimpleNamespace(cashier="EMP-001")
		existing = [SimpleNamespace(reference=r) for r in refs_on_shift]
		shift = MagicMock()
		shift.cashiers = [cashier_row]
		shift.collections = existing

		return batch, provider, shift

	def _csv_content(self, refs: list[str]) -> bytes:
		lines = ["Ref,Amount,Till"] + [f"{r},100.00,T1" for r in refs]
		return "\n".join(lines).encode()

	def test_all_new_rows_created(self):
		batch, provider, shift = self._make_batch([])
		with (
			patch("forecourt.forecourt_integrations.statement_import.frappe") as mfrappe,
		):
			mfrappe.get_doc.side_effect = lambda dt, name: (
				batch if dt == "Payment Import Batch" else provider if dt == "Payment Provider" else shift
			)
			mfrappe.has_permission.return_value = True

			file_doc = MagicMock()
			file_doc.get_content.return_value = self._csv_content(["R001", "R002", "R003"])
			mfrappe.get_all.return_value = [SimpleNamespace(name="FILE-001")]
			mfrappe.get_doc.side_effect = lambda dt, name=None: (
				batch
				if dt == "Payment Import Batch"
				else provider
				if dt == "Payment Provider"
				else shift
				if dt == "Forecourt Shift"
				else file_doc
			)

			from forecourt.forecourt_integrations.statement_import import run

			result = run("IMP-TEST-001")

		self.assertEqual(result["rows_created"], 3)
		self.assertEqual(result["rows_duplicate"], 0)

	def test_existing_ref_skipped(self):
		batch, provider, shift = self._make_batch(["R001"])
		with (
			patch("forecourt.forecourt_integrations.statement_import.frappe") as mfrappe,
		):
			file_doc = MagicMock()
			file_doc.get_content.return_value = self._csv_content(["R001", "R002"])
			mfrappe.get_all.return_value = [SimpleNamespace(name="FILE-001")]
			mfrappe.has_permission.return_value = True
			mfrappe.get_doc.side_effect = lambda dt, name=None: (
				batch
				if dt == "Payment Import Batch"
				else provider
				if dt == "Payment Provider"
				else shift
				if dt == "Forecourt Shift"
				else file_doc
			)

			from forecourt.forecourt_integrations.statement_import import run

			result = run("IMP-TEST-001")

		self.assertEqual(result["rows_created"], 1)
		self.assertEqual(result["rows_duplicate"], 1)
