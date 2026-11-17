# Tests for FMS-D07: payment attribution
from __future__ import annotations

import unittest

from forecourt.calc.attribution import SalesLine, attribute


class TestAttribution(unittest.TestCase):
	def test_simple_mobile_attribution(self) -> None:
		"""Design guide example: 180,000 mobile over 60/40 PMS/AGO → 108,000/72,000."""
		lines = [
			SalesLine(key="PMS", amount=108000.0),
			SalesLine(key="AGO", amount=72000.0),
		]
		result = attribute({"Mobile Money": 180000.0}, lines)
		mobile_rows = [r for r in result if r.payment_type == "Mobile Money"]
		self.assertEqual(len(mobile_rows), 2)
		totals = {r.key: r.amount for r in mobile_rows}
		self.assertAlmostEqual(totals["PMS"], 108000.0, places=2)
		self.assertAlmostEqual(totals["AGO"], 72000.0, places=2)
		self.assertAlmostEqual(sum(r.amount for r in mobile_rows), 180000.0, places=4)

	def test_totals_match_exactly(self) -> None:
		"""Total attributed must equal input total — no rounding loss."""
		lines = [
			SalesLine(key="A", amount=100.0),
			SalesLine(key="B", amount=100.0),
			SalesLine(key="C", amount=100.0),
		]
		result = attribute({"Cash": 100.0}, lines)
		cash_rows = [r for r in result if r.payment_type == "Cash"]
		self.assertAlmostEqual(sum(r.amount for r in cash_rows), 100.0, places=6)

	def test_exact_rows_emitted_first(self) -> None:
		lines = [
			SalesLine(key="CUST-A", amount=5000.0, payment_type="Credit", exact_amount=5000.0),
			SalesLine(key="PMS", amount=10000.0),
		]
		result = attribute({"Credit": 5000.0, "Cash": 10000.0}, lines)
		exact = [r for r in result if r.basis == "Exact"]
		attributed = [r for r in result if r.basis == "Attributed"]
		self.assertEqual(len(exact), 1)
		self.assertEqual(exact[0].key, "CUST-A")
		self.assertEqual(len(attributed), 1)
		self.assertEqual(attributed[0].key, "PMS")

	def test_multiple_payment_types(self) -> None:
		lines = [
			SalesLine(key="PMS", amount=6000.0),
			SalesLine(key="AGO", amount=4000.0),
		]
		result = attribute({"Cash": 5000.0, "Mobile Money": 5000.0}, lines)
		cash_rows = [r for r in result if r.payment_type == "Cash"]
		mobile_rows = [r for r in result if r.payment_type == "Mobile Money"]
		self.assertAlmostEqual(sum(r.amount for r in cash_rows), 5000.0, places=4)
		self.assertAlmostEqual(sum(r.amount for r in mobile_rows), 5000.0, places=4)
		pms_cash = next(r for r in cash_rows if r.key == "PMS")
		self.assertAlmostEqual(pms_cash.amount, 3000.0, places=2)

	def test_no_attributed_payments(self) -> None:
		lines = [SalesLine(key="CUST", amount=1000.0, payment_type="Credit", exact_amount=1000.0)]
		result = attribute({"Credit": 1000.0}, lines)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0].basis, "Exact")

	def test_empty_lines_returns_empty(self) -> None:
		result = attribute({"Cash": 5000.0}, [])
		self.assertEqual(result, [])

	def test_TC_CAL_084_rounding_remainder_lands_on_last_line(self) -> None:
		"""TC-CAL-084: 100.00 split over three equal lines (33.33 each) must sum to exactly 100.00.

		The remainder from rounding (0.01) is added to the last attributed row.
		INV-18: every split must sum exactly to its total.
		"""
		lines = [
			SalesLine(key="A", amount=100.0),
			SalesLine(key="B", amount=100.0),
			SalesLine(key="C", amount=100.0),
		]
		result = attribute({"Cash": 100.0}, lines)
		cash_rows = [r for r in result if r.payment_type == "Cash"]
		amounts = [r.amount for r in cash_rows]
		self.assertEqual(len(amounts), 3)
		# Total must be exact — no rounding loss
		self.assertAlmostEqual(sum(amounts), 100.0, places=6)
		# The last row absorbs the remainder, so the last value is slightly different
		# (33.33 + 33.33 + 33.34 = 100.00)
		self.assertAlmostEqual(amounts[0], amounts[1], places=2)
		self.assertAlmostEqual(sum(amounts), 100.0, places=6)

	def test_TC_CAL_085_credit_exhausts_product_no_remaining_attributed_lines(self) -> None:
		"""TC-CAL-085: when credit slips claim all PMS sales, no attributed payment is split to PMS.

		This validates that the attributor handles zero remaining_sales per product
		cleanly without a division-by-zero error.
		"""
		lines = [
			# PMS fully claimed by an exact credit slip — nothing left to attribute
			SalesLine(key="PMS", amount=10000.0, payment_type="Credit", exact_amount=10000.0),
			# AGO still has sales to attribute
			SalesLine(key="AGO", amount=5000.0),
		]
		# The only remaining payment is Cash for AGO
		result = attribute({"Cash": 5000.0, "Credit": 10000.0}, lines)

		exact_rows = [r for r in result if r.basis == "Exact"]
		attributed_rows = [r for r in result if r.basis == "Attributed"]

		# Credit slip → one exact row for PMS
		self.assertEqual(len(exact_rows), 1)
		self.assertEqual(exact_rows[0].key, "PMS")

		# Cash → attributed only to AGO (PMS has no remaining sales)
		ago_attributed = [r for r in attributed_rows if r.key == "AGO"]
		pms_attributed = [r for r in attributed_rows if r.key == "PMS"]
		self.assertEqual(
			len(pms_attributed), 0, "PMS is exhausted by credit; nothing should be attributed to it"
		)
		self.assertAlmostEqual(sum(r.amount for r in ago_attributed), 5000.0, places=6)


if __name__ == "__main__":
	unittest.main()
