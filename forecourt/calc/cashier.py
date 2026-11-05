"""Cashier balance — pure Python, no frappe imports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CashierBalance:
	"""Inputs and computed balance for one cashier (design guide 7.2)."""

	fuel_amount: float = 0.0
	item_amount: float = 0.0
	debt_receipts: float = 0.0
	cash: float = 0.0
	mobile: float = 0.0
	card: float = 0.0
	credit: float = 0.0
	voucher: float = 0.0
	expenses: float = 0.0
	drops: float = 0.0
	opening_float: float = 0.0

	expected: float = field(default=0.0, init=False)
	accounted: float = field(default=0.0, init=False)
	difference: float = field(default=0.0, init=False)


def balance(cb: CashierBalance) -> CashierBalance:
	"""Compute expected, accounted and difference in place.

	expected  = fuel_amount + item_amount + debt_receipts
	accounted = (cash - opening_float) + mobile + card + credit
	            + voucher + expenses + drops
	difference = accounted - expected  (negative = shortage, positive = excess)
	"""
	cb.expected = cb.fuel_amount + cb.item_amount + cb.debt_receipts
	cb.accounted = (
		(cb.cash - cb.opening_float) + cb.mobile + cb.card + cb.credit + cb.voucher + cb.expenses + cb.drops
	)
	cb.difference = cb.accounted - cb.expected
	return cb
