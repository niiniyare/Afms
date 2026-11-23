"""Unit tests for forecourt.reports.common — FMS-R02."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests.classes import UnitTestCase

from forecourt.reports.common import (
	_col_precision,
	base_ledger_filters,
	make_tree_rows,
	no_data_message,
	no_permission_message,
	summary_card,
	total_row_add,
	total_row_rank,
	total_row_reg,
	total_row_wtd,
	validate_date_range,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_COLS = [
	{"fieldname": "station", "fieldtype": "Link", "options": "Station", "width": 120},
	{"fieldname": "qty", "fieldtype": "Float", "precision": 3, "width": 110},
	{"fieldname": "amount", "fieldtype": "Currency", "width": 120},
	{"fieldname": "avg_price", "fieldtype": "Currency", "width": 100},
]

_DATA = [
	{"station": "STA-001", "qty": 100.0, "amount": 20000.0, "avg_price": 200.0},
	{"station": "STA-002", "qty": 200.0, "amount": 44000.0, "avg_price": 220.0},
]


# ---------------------------------------------------------------------------
# validate_date_range
# ---------------------------------------------------------------------------


class TestValidateDateRange(UnitTestCase):
	def test_valid_range(self):
		self.assertIsNone(validate_date_range("2026-01-01", "2026-03-31"))

	def test_from_after_to(self):
		result = validate_date_range("2026-04-01", "2026-03-01")
		self.assertIn("FMS-R801", result)

	def test_range_too_long(self):
		result = validate_date_range("2025-01-01", "2026-06-01", max_days=366)
		self.assertIn("FMS-R802", result)

	def test_range_exact_max(self):
		# 365 days (non-leap year)
		self.assertIsNone(validate_date_range("2025-01-01", "2025-12-31", max_days=366))

	def test_missing_dates(self):
		self.assertIsNone(validate_date_range(None, "2026-01-01"))
		self.assertIsNone(validate_date_range("2026-01-01", None))

	def test_same_day_range(self):
		# from == to is a valid single-day range
		self.assertIsNone(validate_date_range("2026-01-15", "2026-01-15"))

	def test_range_at_max_366_leap_year(self):
		# 2024 is a leap year: Jan 1 → Dec 31 = 366-day span, within max 366
		self.assertIsNone(validate_date_range("2024-01-01", "2024-12-31", max_days=366))

	def test_range_at_367_days(self):
		# 2024-01-01 → 2025-01-01 spans 367 days (366+1) — exceeds max 366
		result = validate_date_range("2024-01-01", "2025-01-01", max_days=366)
		self.assertIn("FMS-R802", result)

	def test_missing_both_dates(self):
		self.assertIsNone(validate_date_range(None, None))


# ---------------------------------------------------------------------------
# base_ledger_filters
# ---------------------------------------------------------------------------


class TestBaseLedgerFilters(UnitTestCase):
	def test_default_excludes_cancelled_and_superseded(self):
		f = base_ledger_filters({})
		self.assertEqual(f["is_cancelled"], 0)
		self.assertEqual(f["superseded_by"], ["is", "not set"])

	def test_include_history_omits_exclusions(self):
		f = base_ledger_filters({}, include_history=True)
		self.assertNotIn("is_cancelled", f)
		self.assertNotIn("superseded_by", f)

	def test_returns_empty_dict_on_include_history(self):
		f = base_ledger_filters({}, include_history=True)
		self.assertEqual(f, {})


# ---------------------------------------------------------------------------
# T-ADD totals
# ---------------------------------------------------------------------------


class TestTotalRowAdd(UnitTestCase):
	def test_sums_numeric_columns(self):
		row = total_row_add(_DATA, _COLS)
		self.assertEqual(row["qty"], 300.0)
		self.assertEqual(row["amount"], 64000.0)

	def test_first_text_column_gets_label(self):
		row = total_row_add(_DATA, _COLS, label="Grand Total")
		self.assertEqual(row["station"], "Grand Total")

	def test_default_label(self):
		row = total_row_add(_DATA, _COLS)
		self.assertEqual(row["station"], "Total")

	def test_bold_flag(self):
		row = total_row_add(_DATA, _COLS)
		self.assertEqual(row["bold"], 1)

	def test_empty_data(self):
		row = total_row_add([], _COLS)
		self.assertEqual(row["qty"], 0.0)
		self.assertEqual(row["amount"], 0.0)


# ---------------------------------------------------------------------------
# T-WTD totals
# ---------------------------------------------------------------------------


class TestTotalRowWtd(UnitTestCase):
	_COMPUTED: ClassVar[list[dict]] = [
		{
			"fieldname": "avg_price",
			"numerator": "amount",
			"denominator": "qty",
			"multiplier": 1,
			"precision": 2,
		}
	]

	def test_sums_additive_cols(self):
		row = total_row_wtd(_DATA, _COLS, computed=self._COMPUTED)
		self.assertEqual(row["qty"], 300.0)
		self.assertEqual(row["amount"], 64000.0)

	def test_weighted_avg_price(self):
		# (20000 + 44000) / (100 + 200) = 64000 / 300 ≈ 213.33
		row = total_row_wtd(_DATA, _COLS, computed=self._COMPUTED)
		self.assertAlmostEqual(row["avg_price"], 213.33, places=2)

	def test_zero_denominator_returns_zero(self):
		data = [{"station": "X", "qty": 0.0, "amount": 0.0, "avg_price": 0.0}]
		row = total_row_wtd(data, _COLS, computed=self._COMPUTED)
		self.assertEqual(row["avg_price"], 0.0)

	def test_variance_pct_computed(self):
		cols = [
			{"fieldname": "label", "fieldtype": "Data", "width": 120},
			{"fieldname": "sales_l", "fieldtype": "Float", "precision": 3, "width": 100},
			{"fieldname": "variance_l", "fieldtype": "Float", "precision": 3, "width": 100},
			{"fieldname": "variance_pct", "fieldtype": "Percent", "width": 90},
		]
		data = [
			{"label": "A", "sales_l": 1000.0, "variance_l": 10.0, "variance_pct": 1.0},
			{"label": "B", "sales_l": 2000.0, "variance_l": 30.0, "variance_pct": 1.5},
		]
		computed = [
			{
				"fieldname": "variance_pct",
				"numerator": "variance_l",
				"denominator": "sales_l",
				"multiplier": 100,
				"precision": 2,
			}
		]
		row = total_row_wtd(data, cols, computed=computed)
		# (10 + 30) / (1000 + 2000) * 100 = 40/3000*100 ≈ 1.33
		self.assertAlmostEqual(row["variance_pct"], 1.33, places=2)


# ---------------------------------------------------------------------------
# T-REG totals
# ---------------------------------------------------------------------------


class TestTotalRowReg(UnitTestCase):
	def test_sums_and_has_bold(self):
		row = total_row_reg(_DATA, _COLS)
		self.assertEqual(row["qty"], 300.0)
		self.assertEqual(row["bold"], 1)

	def test_count_in_named_col(self):
		cols = [
			{"fieldname": "txn_id", "fieldtype": "Data", "width": 120},
			{"fieldname": "amount", "fieldtype": "Currency", "width": 120},
		]
		data = [
			{"txn_id": "T1", "amount": 100.0},
			{"txn_id": "T2", "amount": 200.0},
		]
		row = total_row_reg(data, cols, count_label="txn_id")
		self.assertEqual(row["txn_id"], 2)
		self.assertEqual(row["amount"], 300.0)


# ---------------------------------------------------------------------------
# T-RANK totals
# ---------------------------------------------------------------------------


class TestTotalRowRank(UnitTestCase):
	def test_averages_non_zero(self):
		data = [
			{"station": "A", "qty": 100.0, "amount": 20000.0, "avg_price": 200.0},
			{"station": "B", "qty": 200.0, "amount": 44000.0, "avg_price": 220.0},
			{"station": "C", "qty": 0.0, "amount": 0.0, "avg_price": 0.0},
		]
		row = total_row_rank(data, _COLS)
		# qty: average of 100, 200 (zero row skipped) = 150
		self.assertAlmostEqual(row["qty"], 150.0)

	def test_default_label(self):
		row = total_row_rank(_DATA, _COLS)
		self.assertEqual(row["station"], "Network Average")

	def test_bold(self):
		row = total_row_rank(_DATA, _COLS)
		self.assertEqual(row["bold"], 1)


# ---------------------------------------------------------------------------
# make_tree_rows
# ---------------------------------------------------------------------------


class TestMakeTreeRows(UnitTestCase):
	_flat: ClassVar[list[dict]] = [
		{"cashier": "EMP-001", "station": "STA-001", "amount": 100.0},
		{"cashier": "EMP-001", "station": "STA-002", "amount": 200.0},
		{"cashier": "EMP-002", "station": "STA-001", "amount": 150.0},
	]

	def test_group_rows_have_indent_0(self):
		rows = make_tree_rows(self._flat, "cashier")
		group_rows = [r for r in rows if r.get("indent") == 0]
		self.assertEqual(len(group_rows), 2)

	def test_detail_rows_have_indent_1(self):
		rows = make_tree_rows(self._flat, "cashier")
		detail_rows = [r for r in rows if r.get("indent") == 1]
		self.assertEqual(len(detail_rows), 3)

	def test_total_row_count(self):
		rows = make_tree_rows(self._flat, "cashier")
		self.assertEqual(len(rows), 5)  # 2 groups + 3 detail

	def test_group_bold(self):
		rows = make_tree_rows(self._flat, "cashier")
		for r in rows:
			if r.get("indent") == 0:
				self.assertEqual(r.get("bold"), 1)

	def test_custom_group_label(self):
		rows = make_tree_rows(self._flat, "cashier", group_label_fn=lambda v: f"[{v}]")
		group_labels = [r["cashier"] for r in rows if r.get("indent") == 0]
		self.assertTrue(all(lbl.startswith("[") for lbl in group_labels))

	def test_group_total_fn(self):
		def total_fn(gv, rows):
			return {"amount": sum(r["amount"] for r in rows)}

		result = make_tree_rows(self._flat, "cashier", group_total_fn=total_fn)
		group_rows = [r for r in result if r.get("indent") == 0]
		totals = {r["cashier"]: r["amount"] for r in group_rows}
		self.assertEqual(totals["EMP-001"], 300.0)
		self.assertEqual(totals["EMP-002"], 150.0)

	def test_sort_key(self):
		rows = make_tree_rows(self._flat, "cashier", sort_key=lambda v: v)
		group_keys = [r["cashier"] for r in rows if r.get("indent") == 0]
		self.assertEqual(group_keys, sorted(group_keys))

	def test_empty_data(self):
		self.assertEqual(make_tree_rows([], "cashier"), [])


# ---------------------------------------------------------------------------
# summary_card
# ---------------------------------------------------------------------------


class TestSummaryCard(UnitTestCase):
	def test_basic(self):
		card = summary_card(1234.5, "Total Revenue", datatype="Currency", indicator="Green")
		self.assertEqual(card["value"], 1234.5)
		self.assertEqual(card["label"], "Total Revenue")
		self.assertEqual(card["indicator"], "Green")
		self.assertNotIn("currency", card)

	def test_with_currency(self):
		card = summary_card(100, "Sales", currency="USD")
		self.assertEqual(card["currency"], "USD")

	def test_defaults(self):
		card = summary_card(0, "X")
		self.assertEqual(card["datatype"], "Float")
		self.assertEqual(card["indicator"], "Blue")


# ---------------------------------------------------------------------------
# message helpers
# ---------------------------------------------------------------------------


class TestMessages(UnitTestCase):
	def test_no_data_message_non_empty(self):
		self.assertTrue(len(no_data_message()) > 0)

	def test_no_permission_message_contains_code(self):
		self.assertIn("FMS-R902", no_permission_message())

	def test_no_permission_message_with_detail(self):
		msg = no_permission_message("Station XYZ not in scope.")
		self.assertIn("FMS-R902", msg)
		self.assertIn("XYZ", msg)


# ---------------------------------------------------------------------------
# _col_precision
# ---------------------------------------------------------------------------


class TestColPrecision(UnitTestCase):
	def test_currency_always_2(self):
		self.assertEqual(_col_precision({"fieldtype": "Currency"}), 2)

	def test_float_uses_precision(self):
		self.assertEqual(_col_precision({"fieldtype": "Float", "precision": 3}), 3)

	def test_missing_precision_defaults_3(self):
		self.assertEqual(_col_precision({"fieldtype": "Float"}), 3)

	def test_none_precision_defaults_3(self):
		self.assertEqual(_col_precision({"fieldtype": "Float", "precision": None}), 3)
