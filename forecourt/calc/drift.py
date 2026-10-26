"""Meter drift calculations — pure Python, no frappe imports."""

from __future__ import annotations


def evol_vs_mvol(evol_litres: float, mvol_litres: float) -> float:
	"""Return E-vol - M-vol drift in litres.

	Positive = electronic reads more than mechanical.
	"""
	return evol_litres - mvol_litres


def ecash_vs_evol(ecash_litres: float, evol_litres: float) -> float:
	"""Return (E-cash / price) - E-vol drift in litres."""
	return ecash_litres - evol_litres


def ecash_vs_mvol(ecash_litres: float, mvol_litres: float) -> float:
	"""Return (E-cash / price) - M-vol drift in litres."""
	return ecash_litres - mvol_litres


def within_tolerance(
	drift_l: float,
	basis_litres: float,
	tol_pct: float = 0.5,
	tol_l: float = 2.0,
) -> bool:
	"""Return True if abs(drift_l) is within tolerance.

	The larger of (basis_litres * tol_pct / 100) and tol_l applies,
	so small volumes don't trigger false alerts (design guide 5.3).
	"""
	abs_drift = abs(drift_l)
	limit = max(basis_litres * tol_pct / 100.0, tol_l)
	return abs_drift <= limit
