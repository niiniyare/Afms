# Tests for FMS-D06: cashier balance
from __future__ import annotations

import unittest

from forecourt.calc.cashier import CashierBalance, balance


class TestCashierBalance(unittest.TestCase):
	def test_zero_balance(self) -> None:
		cb = CashierBalance(fuel_amount=10000.0, cash=10500.0, opening_float=500.0)
		balance(cb)
		self.assertAlmostEqual(cb.expected, 10000.0)
		self.assertAlmostEqual(cb.accounted, 10000.0)
		self.assertAlmostEqual(cb.difference, 0.0)

	def test_shortage(self) -> None:
		cb = CashierBalance(fuel_amount=10000.0, cash=9800.0, opening_float=500.0)
		balance(cb)
		self.assertAlmostEqual(cb.difference, -700.0)

	def test_excess(self) -> None:
		cb = CashierBalance(fuel_amount=10000.0, cash=11000.0, opening_float=500.0)
		balance(cb)
		self.assertAlmostEqual(cb.difference, 500.0)

	def test_multi_payment_types(self) -> None:
		cb = CashierBalance(
			fuel_amount=50000.0,
			cash=20000.0,
			opening_float=1000.0,
			mobile=15000.0,
			card=10000.0,
			credit=5000.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.expected, 50000.0)
		self.assertAlmostEqual(cb.accounted, 49000.0)
		self.assertAlmostEqual(cb.difference, -1000.0)

	def test_expenses_add_to_accounted(self) -> None:
		cb = CashierBalance(
			fuel_amount=10000.0,
			cash=10000.0,
			opening_float=0.0,
			expenses=500.0,
		)
		balance(cb)
		# accounted = 10000 + 500 = 10500; expected = 10000; diff = +500
		self.assertAlmostEqual(cb.difference, 500.0)

	def test_drops_add_to_accounted(self) -> None:
		cb = CashierBalance(
			fuel_amount=20000.0,
			cash=10000.0,
			opening_float=0.0,
			drops=10000.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.difference, 0.0)

	def test_formula_expected(self) -> None:
		cb = CashierBalance(
			fuel_amount=180000.0,
			item_amount=5000.0,
			debt_receipts=20000.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.expected, 205000.0)


if __name__ == "__main__":
	unittest.main()
