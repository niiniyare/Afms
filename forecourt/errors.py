"""FMS error codes.

Ranges (design guide 15.3):
  FMS-S1xx  Shift gates and shift entry
  FMS-W1xx  Meters and drift
  FMS-T2xx  Tanks, dips and deliveries
  FMS-P3xx  Posting and accounting setup
  FMS-I4xx  Integrations
  FMS-C5xx  Corrections and cancellation
  FMS-M6xx  Masters and settings (D36, proposed)

Usage:
    from forecourt.errors import FMSValidationError
    raise FMSValidationError("FMS-S101", _("Closing reading below opening on nozzle {0}. Correct the reading or tick Rollover.").format(nozzle))
"""

import frappe
from frappe import _


class FMSValidationError(frappe.ValidationError):
	"""Validation error with a mandatory FMS error code."""

	def __init__(self, code: str, message: str) -> None:
		self.code = code
		super().__init__(f"[{code}] {message}")


class FMSPermissionError(frappe.PermissionError):
	"""Permission error with a mandatory FMS error code."""

	def __init__(self, code: str, message: str) -> None:
		self.code = code
		super().__init__(f"[{code}] {message}")


# ---------------------------------------------------------------------------
# FMS-S1xx  Shift gates
# ---------------------------------------------------------------------------

FMS_S101 = "FMS-S101"  # Closing reading below opening; rollover not ticked
FMS_S102 = "FMS-S102"  # Opening reading does not match previous closing
FMS_S103 = "FMS-S103"  # Tank has no closing dip
FMS_S104 = "FMS-S104"  # Nozzle reading row has no cashier
FMS_S105 = "FMS-S105"  # Cashier has unclassified difference
FMS_S106 = "FMS-S106"  # Tank variance outside tolerance without reason/approval
FMS_S107 = "FMS-S107"  # Customer over credit limit without approval
FMS_S108 = "FMS-S108"  # Credit litres exceed metered litres for product
FMS_S109 = "FMS-S109"  # Expense line missing type or above limit
FMS_S110 = "FMS-S110"  # Shift window overlaps another submitted shift
FMS_S111 = "FMS-S111"  # Payment feed entries not assigned to a cashier
FMS_S112 = "FMS-S112"  # Price segment has no meter readings
FMS_S113 = "FMS-S113"  # Draft Fuel Own Use entry in shift window
FMS_S114 = "FMS-S114"  # Duplicate mobile money / card reference
FMS_S115 = "FMS-S115"  # Test volume above nozzle per-shift limit (D29, proposed)

# ---------------------------------------------------------------------------
# FMS-W1xx  Meters and drift
# ---------------------------------------------------------------------------

FMS_W102 = "FMS-W102"  # Meter value exceeds nozzle maximum
FMS_W103 = "FMS-W103"  # Meter drift beyond tolerance without reason

# ---------------------------------------------------------------------------
# FMS-T2xx  Tanks, dips and deliveries
# ---------------------------------------------------------------------------

FMS_T201 = "FMS-T201"  # No calibration chart valid on date (chart mode only)
FMS_T202 = "FMS-T202"  # Dip exceeds chart maximum depth
FMS_T203 = "FMS-T203"  # Tank rose without a submitted GRN explaining the rise
FMS_T204 = "FMS-T204"  # Draft GRN in the shift window
FMS_T205 = "FMS-T205"  # Delivery shortage beyond tolerance without reason
FMS_T206 = "FMS-T206"  # GRN missing delivery dip for a required tank

# ---------------------------------------------------------------------------
# FMS-P3xx  Posting and accounting setup
# ---------------------------------------------------------------------------

FMS_P301 = "FMS-P301"  # Mode of Payment has no account for company
FMS_P302 = "FMS-P302"  # Negative stock in tank warehouse

# ---------------------------------------------------------------------------
# FMS-I4xx  Integrations
# ---------------------------------------------------------------------------

FMS_I401 = "FMS-I401"  # Payment feed message failed to parse or map

# ---------------------------------------------------------------------------
# FMS-C5xx  Corrections and cancellation
# ---------------------------------------------------------------------------

FMS_C501 = "FMS-C501"  # Shift Correction needs director approval
FMS_C502 = "FMS-C502"  # Shift-generated document cannot be cancelled directly
FMS_C503 = "FMS-C503"  # Only latest closed shift at station can be cancelled

# ---------------------------------------------------------------------------
# FMS-M6xx  Masters and settings (D36, proposed)
# ---------------------------------------------------------------------------

FMS_M601 = "FMS-M601"  # Station code does not match pattern
FMS_M602 = "FMS-M602"  # Account belongs to wrong company or wrong type
FMS_M603 = "FMS-M603"  # Sales basis not consistent with recorded meters
FMS_M604 = "FMS-M604"  # Tank capacity or safe fill invalid
FMS_M605 = "FMS-M605"  # Calibration chart depths/volumes not strictly increasing
FMS_M606 = "FMS-M606"  # Nozzle tank belongs to another station
FMS_M607 = "FMS-M607"  # Last nozzle readings can only be changed by a shift or Meter Change
FMS_M630 = "FMS-M630"  # Station Group has children — cannot unset Is Group
