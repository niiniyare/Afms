"""Fiscal Adapter interface — FMS-J07.

All fiscal adapters must implement FiscalAdapter.  Each method receives a
frappe.Document (Sales Invoice or POS Invoice) and returns a FiscalResult.

Architecture rule: no country names in core code.  The adapter class is
chosen at runtime from ``Forecourt Company Settings.fiscal_adapter``.

Supported adapter identifiers (from Forecourt Company Settings):
  "eTIMS Kenya"   → etims.KenyaETIMSAdapter
  ""  (empty)     → no-op (fiscalisation disabled)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class FiscalResult:
	"""Outcome of one fiscal API call."""

	success: bool
	receipt_no: str = ""
	signature: str = ""
	qr_data: str = ""
	error: str = ""
	raw: dict = field(default_factory=dict)


@runtime_checkable
class FiscalAdapter(Protocol):
	"""Protocol every fiscal adapter must satisfy."""

	def submit(self, invoice: object) -> FiscalResult:
		"""Fiscalise a submitted invoice; return receipt details."""
		...

	def status(self, invoice: object) -> FiscalResult:
		"""Check the current fiscalisation status of an invoice."""
		...

	def cancel(self, invoice: object) -> FiscalResult:
		"""Cancel / credit a previously fiscalised invoice."""
		...


_REGISTRY: dict[str, str] = {
	"eTIMS Kenya": "forecourt.forecourt_integrations.fiscal_adapters.etims.KenyaETIMSAdapter",
}


def get_adapter(adapter_name: str) -> FiscalAdapter | None:
	"""Return an instantiated adapter for *adapter_name*, or None if disabled."""
	if not adapter_name:
		return None
	dotted = _REGISTRY.get(adapter_name)
	if not dotted:
		import frappe

		frappe.log_error(
			f"Unknown fiscal adapter: {adapter_name!r}.  Registered adapters: {list(_REGISTRY)}",
			"Fiscal Adapter",
		)
		return None
	import frappe

	cls = frappe.get_attr(dotted)
	return cls()
