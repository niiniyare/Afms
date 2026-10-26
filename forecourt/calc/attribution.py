"""Payment attribution for the Sales Ledger — pure Python, no frappe imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SalesLine:
	"""One nozzle or item sales line to be attributed."""

	key: str
	amount: float
	payment_type: str = ""
	exact_amount: float = 0.0


@dataclass
class AttributedRow:
	"""One Sales Ledger row after attribution."""

	key: str
	payment_type: str
	amount: float
	basis: str


def attribute(
	total_by_type: dict[str, float],
	sales_lines: list[SalesLine],
) -> list[AttributedRow]:
	"""Spread payments over sales lines by value (design guide 10.4).

	1. Exact rows (credit slips, POS invoices) are emitted first with
	   basis="Exact".
	2. Remaining payment totals are spread proportionally over the
	   remaining sales value; the last row of each payment type absorbs
	   rounding so totals match exactly.

	Raises ValueError if attributed payments remain but no unattributed
	sales lines exist to receive them.
	"""
	rows: list[AttributedRow] = []

	# Step 1: emit exact rows and track remaining sales per key
	remaining_sales: dict[str, float] = {}
	exact_by_type: dict[str, float] = {}
	for line in sales_lines:
		if line.payment_type and line.exact_amount > 0:
			rows.append(
				AttributedRow(
					key=line.key,
					payment_type=line.payment_type,
					amount=line.exact_amount,
					basis="Exact",
				)
			)
			exact_by_type[line.payment_type] = exact_by_type.get(line.payment_type, 0.0) + line.exact_amount
		remaining = line.amount - line.exact_amount
		if remaining > 0:
			remaining_sales[line.key] = remaining

	total_remaining_sales = sum(remaining_sales.values())

	# Step 2: attributed payments
	attributed_by_type: dict[str, float] = {}
	for ptype, total in total_by_type.items():
		attributed = total - exact_by_type.get(ptype, 0.0)
		if attributed > 0:
			attributed_by_type[ptype] = attributed

	if not attributed_by_type or not remaining_sales:
		return rows

	if total_remaining_sales <= 0:
		raise ValueError("Attributed payments remain but no unattributed sales lines exist.")

	for ptype, attributed_total in attributed_by_type.items():
		keys = list(remaining_sales.keys())
		allocated = 0.0
		for i, key in enumerate(keys):
			proportion = remaining_sales[key] / total_remaining_sales
			if i == len(keys) - 1:
				amount = round(attributed_total - allocated, 6)
			else:
				amount = round(attributed_total * proportion, 6)
			rows.append(AttributedRow(key=key, payment_type=ptype, amount=amount, basis="Attributed"))
			allocated += amount

	return rows
