"""Shift Correction applier: cashier (FMS-G0x — implemented in task G0x)."""

from __future__ import annotations

import frappe
from frappe import _


def apply(correction) -> None:
	frappe.throw(_("Correction type '{0}' is not yet implemented.").format(correction.correction_type))
