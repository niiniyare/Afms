"""Calibration chart interpolation — pure Python, no frappe imports."""

from __future__ import annotations


def interpolate(depth_mm: float, rows: list[tuple[float, float]]) -> float:
	"""Return volume in litres for the given depth using linear interpolation.

	rows: list of (depth_mm, volume_l) sorted pairs, strictly increasing.
	Raises ValueError for out-of-range depth or empty chart.
	"""
	if not rows:
		raise ValueError("Calibration chart has no rows.")
	min_depth = rows[0][0]
	max_depth = rows[-1][0]
	if depth_mm < min_depth:
		raise ValueError(f"Depth {depth_mm} mm is below chart minimum ({min_depth} mm).")
	if depth_mm > max_depth:
		raise ValueError(f"Depth {depth_mm} mm exceeds chart maximum ({max_depth} mm).")
	for d, v in rows:
		if d == depth_mm:
			return v
	for i in range(len(rows) - 1):
		d0, v0 = rows[i]
		d1, v1 = rows[i + 1]
		if d0 < depth_mm < d1:
			fraction = (depth_mm - d0) / (d1 - d0)
			return v0 + fraction * (v1 - v0)
	raise ValueError(f"Depth {depth_mm} mm not bracketed by chart rows.")


def net_volume(
	depth_mm: float,
	product_rows: list[tuple[float, float]],
	water_rows: list[tuple[float, float]] | None = None,
	water_dip_mm: float = 0.0,
) -> float:
	"""Return net product volume = product volume - water volume.

	water_rows: calibration chart for water layer (same format as product_rows).
	water_dip_mm: measured water depth; 0 means no water detected.
	Raises ValueError if depths are out of range.
	"""
	product_vol = interpolate(depth_mm, product_rows)
	if not water_rows or not water_dip_mm:
		return product_vol
	water_vol = interpolate(water_dip_mm, water_rows)
	return product_vol - water_vol


def validate_rows(rows: list[tuple[float, float]]) -> list[str]:
	"""Return list of error messages; empty list means the chart is valid."""
	errors: list[str] = []
	if len(rows) < 2:
		errors.append("Chart must have at least two rows.")
		return errors
	prev_d, prev_v = rows[0]
	for i, (d, v) in enumerate(rows[1:], start=2):
		if d <= prev_d:
			errors.append(f"Row {i}: depth {d} mm must be greater than row {i - 1} ({prev_d} mm).")
		if v <= prev_v:
			errors.append(f"Row {i}: volume {v} L must be greater than row {i - 1} ({prev_v} L).")
		prev_d, prev_v = d, v
	return errors
