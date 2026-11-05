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


if __name__ == "__main__":
	unittest.main()
