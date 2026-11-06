"""FMS-U06: Shift close readiness panel — server entry point.

Calls ``ForecourtShift.get_close_readiness()`` which runs all gates and
returns a structured summary the client renders without page navigation.

Return shape::

    {
        "state": "Blocked" | "Waiting" | "Attention" | "Ready",
        "items": [
            {
                "code":     str,         # e.g. "FMS-S101"
                "severity": str,         # "blocking" | "waiting" | "attention"
                "area":     str,         # translated area label
                "message":  str,         # human-readable, code-prefixed
                "fix":      str,         # actionable instruction
                "tab":      str | None,  # fieldname of tab to navigate to
                "table":    str | None,  # fieldname of child table
            },
            ...
        ],
    }
"""

from __future__ import annotations

import frappe
from frappe import _

from forecourt.errors import fms_error_wrapper


@frappe.whitelist()
def get_close_readiness(shift_name: str) -> dict:
    """Return close-readiness data for the given shift.

    Raises ``frappe.PermissionError`` if the caller cannot read the shift.
    Unexpected exceptions are caught by the ``fms_error_wrapper`` and
    re-raised as FMS-P399 so station roles never see a raw traceback.
    """
    with fms_error_wrapper("get_close_readiness"):
        shift = frappe.get_doc("Forecourt Shift", shift_name)
        frappe.has_permission("Forecourt Shift", doc=shift, throw=True)
        return shift.get_close_readiness()
