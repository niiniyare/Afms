"""Meter delta calculations — pure Python, no frappe imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MeterReading:
	"""A single reading of one meter (E-cash, E-vol or M-vol)."""

	opening: float
	closing: float
	rollover_max: float = 0.0
	rollover: bool = False


@dataclass
class SegmentSales:
	"""Computed sales for one nozzle price segment."""

	ecash_delta: float
	evol_delta: float
	mvol_delta: float
	ecash_litres: float
	evol_litres: float
	mvol_litres: float
	basis: str
	basis_litres: float
	basis_amount: float


def meter_delta(reading: MeterReading) -> float:
	"""Return the meter delta, handling rollover.

	Raises ValueError if closing < opening and rollover is not flagged,
	if rollover_max is 0 when rollover is True, or if closing exceeds
	rollover_max (a physical impossibility for that meter).
	"""
	if reading.rollover_max > 0 and reading.closing > reading.rollover_max:
		raise ValueError(
			f"Closing reading {reading.closing} exceeds rollover maximum {reading.rollover_max}."
		)
	if reading.closing >= reading.opening:
		return reading.closing - reading.opening
	if not reading.rollover:
		raise ValueError(
			f"Closing reading {reading.closing} < opening {reading.opening}. "
			"Tick Rollover if the meter rolled over."
		)
	if reading.rollover_max <= 0:
		raise ValueError(
			"Rollover is ticked but rollover_max is 0 or not set. "
			"Set the meter rollover maximum on the Nozzle."
		)
	if reading.closing > reading.rollover_max:
		raise ValueError(
			f"Closing reading {reading.closing} exceeds rollover maximum {reading.rollover_max}."
		)
	return (reading.rollover_max - reading.opening) + reading.closing


def segment_sales(
	ecash: MeterReading | None,
	evol: MeterReading | None,
	mvol: MeterReading | None,
	price: float,
	sales_basis: str,
) -> SegmentSales:
	"""Compute sales for one price segment on one nozzle.

	sales_basis: "Elec Cash" | "Elec Mtr" | "Man Mtr" | "Highest"
	Raises ValueError for unsupported basis or missing required meter.
	"""
	if price <= 0:
		raise ValueError(f"Price must be positive, got {price}.")

	ecash_delta = meter_delta(ecash) if ecash is not None else 0.0
	evol_delta = meter_delta(evol) if evol is not None else 0.0
	mvol_delta = meter_delta(mvol) if mvol is not None else 0.0

	ecash_litres = ecash_delta / price if ecash is not None else 0.0
	evol_litres = evol_delta
	mvol_litres = mvol_delta

	valid_bases = {"Elec Cash", "Elec Mtr", "Man Mtr", "Highest"}
	if sales_basis not in valid_bases:
		raise ValueError(f"Unknown sales_basis '{sales_basis}'. Must be one of {valid_bases}.")

	if sales_basis == "Elec Cash":
		if ecash is None:
			raise ValueError("Sales basis is Elec Cash but no E-cash reading provided.")
		basis = "Elec Cash"
		basis_litres = ecash_litres
		basis_amount = ecash_delta

	elif sales_basis == "Elec Mtr":
		if evol is None:
			raise ValueError("Sales basis is Elec Mtr but no E-vol reading provided.")
		basis = "Elec Mtr"
		basis_litres = evol_litres
		basis_amount = evol_litres * price

	elif sales_basis == "Man Mtr":
		if mvol is None:
			raise ValueError("Sales basis is Man Mtr but no M-vol reading provided.")
		basis = "Man Mtr"
		basis_litres = mvol_litres
		basis_amount = mvol_litres * price

	else:  # Highest
		candidates: list[tuple[float, str]] = []
		if ecash is not None:
			candidates.append((ecash_litres, "Elec Cash"))
		if evol is not None:
			candidates.append((evol_litres, "Elec Mtr"))
		if mvol is not None:
			candidates.append((mvol_litres, "Man Mtr"))
		if not candidates:
			raise ValueError("Sales basis is Highest but no meter readings provided.")
		basis_litres, basis = max(candidates, key=lambda x: x[0])
		basis_amount = ecash_delta if basis == "Elec Cash" else basis_litres * price

	return SegmentSales(
		ecash_delta=ecash_delta,
		evol_delta=evol_delta,
		mvol_delta=mvol_delta,
		ecash_litres=ecash_litres,
		evol_litres=evol_litres,
		mvol_litres=mvol_litres,
		basis=basis,
		basis_litres=basis_litres,
		basis_amount=basis_amount,
	)
