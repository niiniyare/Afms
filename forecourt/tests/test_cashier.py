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

	def test_TC_CAL_070_worked_example_8_2(self) -> None:
		"""TC-CAL-070: exact worked example from fms.md 8.2 (Cashier Amina, Westlands Day shift).

		PMS 1200 L x 180 = 216,000 + AGO 900 L x 170 = 153,000 + Lubricants 3,500
		→ Expected = 372,500.
		Accounted: cash 121,500 - float 5,000 = 116,500 + credit 34,000 + mobile 180,000
		           + card 40,000 + expense 1,500 = 372,000.
		Difference = 372,000 - 372,500 = -500 (shortage).
		"""
		cb = CashierBalance(
			fuel_amount=369000.0,  # 216,000 + 153,000
			item_amount=3500.0,  # lubricants
			debt_receipts=0.0,
			cash=121500.0,
			opening_float=5000.0,
			credit=34000.0,
			mobile=180000.0,
			card=40000.0,
			expenses=1500.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.expected, 372500.0)
		self.assertAlmostEqual(cb.accounted, 372000.0)
		self.assertAlmostEqual(cb.difference, -500.0)

	def test_TC_CAL_071_cash_counted_below_float(self) -> None:
		"""TC-CAL-071: cash counted below float → negative cash-for-shift; reduces accounted."""
		cb = CashierBalance(
			fuel_amount=10000.0,
			cash=3000.0,
			opening_float=5000.0,
		)
		balance(cb)
		# cash - float = 3000 - 5000 = -2000
		self.assertAlmostEqual(cb.accounted, -2000.0)
		self.assertAlmostEqual(cb.difference, -12000.0)

	def test_TC_CAL_072_debt_receipt_moves_expected_and_accounted(self) -> None:
		"""TC-CAL-072: debt receipt raises both expected and accounted; difference unchanged."""
		cb_no_debt = CashierBalance(fuel_amount=10000.0, cash=10000.0, opening_float=0.0)
		balance(cb_no_debt)
		diff_before = cb_no_debt.difference

		cb = CashierBalance(
			fuel_amount=10000.0,
			debt_receipts=5000.0,
			cash=15000.0,
			opening_float=0.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.expected, 15000.0)
		self.assertAlmostEqual(cb.accounted, 15000.0)
		self.assertAlmostEqual(cb.difference, diff_before)  # unchanged

	def test_TC_CAL_074_pure_credit_sale_zero_difference(self) -> None:
		"""TC-CAL-074: cashier whose only sales are credit slips has zero difference.

		Fuel amount = credit value; credit collection = same value → difference 0.
		"""
		cb = CashierBalance(
			fuel_amount=34000.0,  # AGO 200 L x 170
			credit=34000.0,
			opening_float=0.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.difference, 0.0)

	def test_TC_CAL_075_cashier_no_collections_at_all(self) -> None:
		"""TC-CAL-075: cashier with readings but zero collections → difference = -expected."""
		fuel = 50000.0
		cb = CashierBalance(fuel_amount=fuel, opening_float=0.0)
		balance(cb)
		self.assertAlmostEqual(cb.expected, fuel)
		self.assertAlmostEqual(cb.accounted, 0.0)
		self.assertAlmostEqual(cb.difference, -fuel)

	def test_TC_CAL_076_collections_but_no_readings_excess(self) -> None:
		"""TC-CAL-076: cashier collected cash for a colleague with no nozzle readings.

		Expected = 0; accounted = cash collected → excess = +amount.
		"""
		cb = CashierBalance(
			fuel_amount=0.0,
			cash=20000.0,
			opening_float=0.0,
		)
		balance(cb)
		self.assertAlmostEqual(cb.expected, 0.0)
		self.assertAlmostEqual(cb.accounted, 20000.0)
		self.assertAlmostEqual(cb.difference, 20000.0)  # excess, must be resolved


if __name__ == "__main__":
	unittest.main()
