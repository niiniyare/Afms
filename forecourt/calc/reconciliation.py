"""Tank reconciliation — pure Python, no frappe imports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TankReconciliation:
	"""Inputs and outputs for one tank's shift reconciliation (design guide 5.5)."""

	opening_volume: float
	receipts: float = 0.0
	net_sales: float = 0.0
	own_use: float = 0.0
	transfers: float = 0.0
	closing_dip: float | None = None

	expected_closing: float = field(default=0.0, init=False)
	variance: float | None = field(default=None, init=False)
	variance_pct: float | None = field(default=None, init=False)


def reconcile(rec: TankReconciliation) -> TankReconciliation:
	"""Compute expected_closing and, if closing_dip provided, variance.

	Variance % is relative to net_sales; None when net_sales is zero.
	Returns the same object mutated in place.
	"""
	rec.expected_closing = rec.opening_volume + rec.receipts - rec.net_sales - rec.own_use + rec.transfers
	if rec.closing_dip is not None:
		rec.variance = rec.closing_dip - rec.expected_closing
		rec.variance_pct = (rec.variance / rec.net_sales * 100.0) if rec.net_sales else None
	return rec


def within_tolerance(
	variance_l: float,
	net_sales: float,
	tol_pct: float = 0.5,
	tol_l: float = 20.0,
) -> bool:
	"""Return True if abs(variance_l) is within tolerance.

	The *larger* of tol_l and (net_sales * tol_pct / 100) applies,
	so tiny sales don't trigger alerts (design guide 5.6).
	"""
	abs_var = abs(variance_l)
	limit = max(tol_l, net_sales * tol_pct / 100.0)
	return abs_var <= limit
