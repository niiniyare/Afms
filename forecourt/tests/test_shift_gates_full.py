"""Comprehensive unit tests for all Forecourt Shift before_submit gates.

Each gate method collects structured items into a list[dict].  Every test
in this file calls a gate directly, without initialising a Frappe site,
by patching translation helpers and replacing frappe.db with a MagicMock.

Gate item keys guaranteed by every gate:
    code       e.g. "FMS-S102"
    severity   "blocking" | "waiting" | "attention"
    area       translated label string
    message    human-readable, includes the code
    fix        actionable instruction
    tab        fieldname of the form tab, or None
    table      fieldname of the child table, or None

Covered in this file (the basic S101/S104/S105/S108/S115 cases are in
test_shift_gates.py):
    FMS-S102   Opening reading does not match the previous shift's closing
    FMS-S103   Tank has no closing dip when dips are required
    FMS-S106   Tank variance outside tolerance — no reason or not approved
    FMS-S107   Over-limit credit sale requires approval
    FMS-S109   Expense line missing type or above per-line limit
    FMS-S110   Shift window overlaps a submitted shift at this station
    FMS-S112   Price segment has no meter readings
    FMS-S113   Draft Fuel Own Use entry exists inside the shift window
    FMS-S114   Duplicate mobile money / card reference
    FMS-S116   Shift has pending or rejected approvals
    FMS-W103   Meter drift beyond tolerance — reason required

See test-cases.md sections 18 (Shift Gates) and 6 (Calculations) for the
full catalogue.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_MODULE = "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift"

_TRANS_PATCHER = patch(f"{_MODULE}._", side_effect=lambda s, *a, **kw: s)
_FLT_PATCHER = patch(
	f"{_MODULE}.flt",
	side_effect=lambda v, p=None, **kw: round(float(v or 0), p) if p is not None else float(v or 0),
)
_GETDATETIME_PATCHER = patch(
	f"{_MODULE}.get_datetime",
	side_effect=lambda s: s,
)


def setUpModule():
	import frappe

	_TRANS_PATCHER.start()
	_FLT_PATCHER.start()
	_GETDATETIME_PATCHER.start()

	frappe.db = MagicMock()
	frappe.db.get_value.return_value = None
	frappe.db.exists.return_value = False
	frappe.db.count.return_value = 0
	frappe.get_all = MagicMock(return_value=[])
	frappe.get_cached_doc = MagicMock()


def tearDownModule():
	_GETDATETIME_PATCHER.stop()
	_FLT_PATCHER.stop()
	_TRANS_PATCHER.stop()


def _make_shift(**kwargs):
	defaults = {
		"name": "TEST-SHIFT-001",
		"station": "STA-001",
		"company": "Test Co",
		"shift_template": "Morning",
		"shift_date": "2026-10-27",
		"shift_start": "2026-10-27 06:00:00",
		"shift_end": "2026-10-27 14:00:00",
		"previous_shift": None,
		"approval_state": "Not Required",
		"meter_readings": [],
		"tank_dips": [],
		"prices": [],
		"cashiers": [],
		"cash_counts": [],
		"credit_sales": [],
		"item_sales": [],
		"collections": [],
		"resolutions": [],
	}
	defaults.update(kwargs)
	return SimpleNamespace(**defaults)


def _row(**kwargs):
	return SimpleNamespace(**kwargs)


def _import_shift():
	from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

	return ForecourtShift


def _run_gate(gate_name: str, **shift_kwargs) -> list[dict]:
	"""Helper: run a named gate on a shift built from shift_kwargs, return items."""
	ForecourtShift = _import_shift()
	doc = _make_shift(**shift_kwargs)
	items: list[dict] = []
	getattr(ForecourtShift, gate_name)(doc, items)
	return items


# ---------------------------------------------------------------------------
# FMS-S102: Opening reading must match the previous shift's closing
# ---------------------------------------------------------------------------


class TestGateReadingContinuity(unittest.TestCase):
	"""FMS-S102: opening readings must equal the previous shift's closings (TC-SHC-005)."""

	def test_no_previous_shift_means_gate_is_skipped(self) -> None:
		"""With no previous shift there is nothing to compare; gate produces no items."""
		items = _run_gate("_gate_reading_continuity", previous_shift=None)
		self.assertEqual(items, [])

	def test_matching_openings_pass_the_gate(self) -> None:
		"""When every opening equals its previous closing the gate produces no items."""
		import frappe

		frappe.get_all.return_value = [
			SimpleNamespace(
				nozzle="N1",
				closing_elec_cash=1000.0,
				closing_elec_meter=0.0,
				closing_man_meter=0.0,
				segment_no=1,
			),
		]
		rows = [
			_row(
				nozzle="N1",
				segment_no=1,
				rec_elec_cash=1,
				opening_elec_cash=1000.0,
				rec_elec_meter=0,
				opening_elec_meter=0.0,
				rec_man_meter=0,
				opening_man_meter=0.0,
			),
		]
		items = _run_gate("_gate_reading_continuity", previous_shift="SHIFT-000", meter_readings=rows)
		self.assertEqual(items, [])

	def test_mismatched_opening_raises_S102_naming_the_nozzle(self) -> None:
		"""TC-SHC-005: opening does not match previous closing → S102 names the nozzle and meter."""
		import frappe

		frappe.get_all.return_value = [
			SimpleNamespace(
				nozzle="N1",
				closing_elec_cash=1000.0,
				closing_elec_meter=0.0,
				closing_man_meter=0.0,
				segment_no=1,
			),
		]
		rows = [
			_row(
				nozzle="N1",
				segment_no=1,
				rec_elec_cash=1,
				opening_elec_cash=900.0,  # mismatch
				rec_elec_meter=0,
				opening_elec_meter=0.0,
				rec_man_meter=0,
				opening_man_meter=0.0,
			),
		]
		items = _run_gate("_gate_reading_continuity", previous_shift="SHIFT-000", meter_readings=rows)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S102")
		self.assertIn("N1", items[0]["message"])

	def test_second_segment_rows_are_ignored_by_continuity_check(self) -> None:
		"""Only segment_no == 1 rows are continuity-checked; handover rows are skipped."""
		import frappe

		frappe.get_all.return_value = [
			SimpleNamespace(
				nozzle="N1",
				closing_elec_cash=1000.0,
				closing_elec_meter=0.0,
				closing_man_meter=0.0,
				segment_no=1,
			),
		]
		rows = [
			_row(
				nozzle="N1",
				segment_no=2,
				rec_elec_cash=1,
				opening_elec_cash=500.0,
				rec_elec_meter=0,
				opening_elec_meter=0.0,
				rec_man_meter=0,
				opening_man_meter=0.0,
			),
		]
		items = _run_gate("_gate_reading_continuity", previous_shift="SHIFT-000", meter_readings=rows)
		self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# FMS-S103: Every tank that requires a closing dip must have one
# ---------------------------------------------------------------------------


class TestGateTankDipsRequired(unittest.TestCase):
	"""FMS-S103: when dips_required is true on the template, every tank must have a closing dip (TC-DIP-001)."""

	def test_dips_not_required_means_gate_is_skipped(self) -> None:
		"""When the template says dips are not required the gate never fires."""
		import frappe

		frappe.db.get_value.return_value = 0  # dips_required = False
		dips = [_row(tank="T1", dip_l=0.0, dip_mm=0.0)]
		items = _run_gate("_gate_tank_dips_required", shift_template="DAY", tank_dips=dips)
		self.assertEqual(items, [])

	def test_dip_present_passes_when_dips_are_required(self) -> None:
		import frappe

		frappe.db.get_value.return_value = 1  # dips_required = True
		dips = [_row(tank="T1", dip_l=15000.0, dip_mm=0.0)]
		items = _run_gate("_gate_tank_dips_required", shift_template="DAY", tank_dips=dips)
		self.assertEqual(items, [])

	def test_missing_dip_fires_S103_naming_the_tank(self) -> None:
		"""TC-DIP-001: required dip missing → S103 names the tank."""
		import frappe

		frappe.db.get_value.return_value = 1  # dips_required = True
		dips = [_row(tank="T1", dip_l=0.0, dip_mm=0.0)]  # both zero = missing
		items = _run_gate("_gate_tank_dips_required", shift_template="DAY", tank_dips=dips)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S103")
		self.assertIn("T1", items[0]["message"])


# ---------------------------------------------------------------------------
# FMS-S106: Tank variance outside tolerance — reason required, approval above threshold
# ---------------------------------------------------------------------------


class TestGateTankVarianceApproved(unittest.TestCase):
	"""FMS-S106: out-of-tolerance variance needs a reason; large variance also needs approval (TC-DIP-002/003)."""

	def test_variance_within_tolerance_passes_regardless_of_reason(self) -> None:
		dips = [_row(tank="T1", within_tolerance=1, reason=None, needs_approval=0, approved_by=None)]
		items = _run_gate("_gate_tank_variance_approved", tank_dips=dips)
		self.assertEqual(items, [])

	def test_out_of_tolerance_variance_without_reason_fires_S106(self) -> None:
		"""TC-DIP-002: variance outside tolerance but no reason typed → S106."""
		dips = [_row(tank="T1", within_tolerance=0, reason=None, needs_approval=0, approved_by=None)]
		items = _run_gate("_gate_tank_variance_approved", tank_dips=dips)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S106")
		self.assertIn("T1", items[0]["message"])

	def test_reason_given_but_needs_approval_and_not_approved_fires_S106(self) -> None:
		"""TC-DIP-003: reason given, but variance exceeds approval threshold and not approved → S106."""
		dips = [
			_row(tank="T1", within_tolerance=0, reason="Suspected theft", needs_approval=1, approved_by=None)
		]
		items = _run_gate("_gate_tank_variance_approved", tank_dips=dips)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S106")

	def test_reason_given_approved_and_outside_tolerance_passes(self) -> None:
		dips = [
			_row(
				tank="T1",
				within_tolerance=0,
				reason="Dip error",
				needs_approval=1,
				approved_by="area.manager@example.com",
			)
		]
		items = _run_gate("_gate_tank_variance_approved", tank_dips=dips)
		self.assertEqual(items, [])

	def test_reason_given_no_approval_needed_passes(self) -> None:
		dips = [_row(tank="T1", within_tolerance=0, reason="Temperature", needs_approval=0, approved_by=None)]
		items = _run_gate("_gate_tank_variance_approved", tank_dips=dips)
		self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# FMS-S107: Over-limit credit sale requires approval
# ---------------------------------------------------------------------------


class TestGateCreditOverLimit(unittest.TestCase):
	"""FMS-S107: credit sales marked over_limit must have an approver before close."""

	def test_all_credit_within_limit_passes(self) -> None:
		credits = [_row(customer="Cust A", slip_no="001", over_limit=0, over_limit_approved_by=None)]
		items = _run_gate("_gate_credit_over_limit", credit_sales=credits)
		self.assertEqual(items, [])

	def test_over_limit_credit_without_approval_fires_S107(self) -> None:
		"""TC-FRD-003 / TC-CSH-004 path: over-limit flag set but no approver → S107."""
		credits = [_row(customer="Coast Haulage", slip_no="042", over_limit=1, over_limit_approved_by=None)]
		items = _run_gate("_gate_credit_over_limit", credit_sales=credits)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S107")
		self.assertIn("Coast Haulage", items[0]["message"])

	def test_over_limit_credit_with_approval_passes(self) -> None:
		credits = [
			_row(customer="Coast Haulage", slip_no="042", over_limit=1, over_limit_approved_by="supervisor")
		]
		items = _run_gate("_gate_credit_over_limit", credit_sales=credits)
		self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# FMS-S109: Expense line must have a type; amount must not exceed per-line limit
# ---------------------------------------------------------------------------


class TestGateExpenses(unittest.TestCase):
	"""FMS-S109: each Expense collection row needs a type and must be within the per-expense limit."""

	def _make_expense_type_mock(self, max_per_line: float) -> SimpleNamespace:
		return SimpleNamespace(max_per_line=max_per_line)

	def test_non_expense_collections_are_ignored(self) -> None:
		collections = [_row(collection_type="Mobile Money", expense_type=None, amount=5000.0, idx=1)]
		items = _run_gate("_gate_expenses", collections=collections)
		self.assertEqual(items, [])

	def test_expense_with_valid_type_and_within_limit_passes(self) -> None:
		import frappe

		frappe.get_cached_doc.return_value = self._make_expense_type_mock(max_per_line=2000.0)
		collections = [_row(collection_type="Expense", expense_type="Cleaning", amount=1500.0, idx=1)]
		items = _run_gate("_gate_expenses", collections=collections)
		self.assertEqual(items, [])

	def test_expense_missing_type_fires_S109(self) -> None:
		"""Expense row with no expense_type → S109 naming the row index."""
		collections = [_row(collection_type="Expense", expense_type=None, amount=1500.0, idx=2)]
		items = _run_gate("_gate_expenses", collections=collections)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S109")
		self.assertIn("2", items[0]["message"])

	def test_expense_exceeding_per_line_limit_fires_S109(self) -> None:
		"""Amount above max_per_line for the expense type → S109."""
		import frappe

		frappe.get_cached_doc.return_value = self._make_expense_type_mock(max_per_line=500.0)
		collections = [
			_row(collection_type="Expense", expense_type="Fuel for generator", amount=800.0, idx=3)
		]
		items = _run_gate("_gate_expenses", collections=collections)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S109")

	def test_expense_with_no_configured_limit_always_passes(self) -> None:
		"""When max_per_line is 0 or None, there is no per-line limit."""
		import frappe

		frappe.get_cached_doc.return_value = self._make_expense_type_mock(max_per_line=0.0)
		collections = [_row(collection_type="Expense", expense_type="Any", amount=99999.0, idx=1)]
		items = _run_gate("_gate_expenses", collections=collections)
		self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# FMS-S110: Shift window must not overlap another submitted shift
# ---------------------------------------------------------------------------


class TestGateNoOverlap(unittest.TestCase):
	"""FMS-S110: overlapping shift windows at the same station are blocked (TC-SHC-007)."""

	def test_no_other_shifts_at_station_passes(self) -> None:
		import frappe

		frappe.db.exists.return_value = False  # no Forecourt Company Settings
		frappe.get_all.return_value = []  # no overlapping shifts
		items = _run_gate(
			"_gate_no_overlap",
			station="STA-001",
			shift_start="2026-10-27 06:00:00",
			shift_end="2026-10-27 18:00:00",
		)
		self.assertEqual(items, [])

	def test_overlapping_submitted_shift_fires_S110(self) -> None:
		"""TC-SHC-007: an overlap with a submitted shift fires S110 naming the conflicting shift."""
		import frappe

		frappe.db.exists.return_value = False
		frappe.get_all.return_value = [SimpleNamespace(name="SHIFT-PREV")]
		items = _run_gate(
			"_gate_no_overlap",
			station="STA-001",
			shift_start="2026-10-27 06:00:00",
			shift_end="2026-10-27 18:00:00",
		)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S110")
		self.assertIn("SHIFT-PREV", items[0]["message"])

	def test_overlap_allowed_by_company_setting_skips_gate(self) -> None:
		"""When allow_overlapping_shifts is set, S110 is not applied."""
		import frappe

		frappe.db.exists.return_value = True  # Forecourt Company Settings exists
		frappe.db.get_value.return_value = 1  # allow_overlapping_shifts = True
		frappe.get_all.return_value = [SimpleNamespace(name="SHIFT-PREV")]
		items = _run_gate(
			"_gate_no_overlap",
			station="STA-001",
			shift_start="2026-10-27 06:00:00",
			shift_end="2026-10-27 18:00:00",
		)
		self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# FMS-S112: Every price segment must have closing meter readings
# ---------------------------------------------------------------------------


class TestGateSegmentReadings(unittest.TestCase):
	"""FMS-S112: each row in the Shift Price table must have matching meter readings (TC-PRC-002)."""

	def test_every_segment_has_readings_passes(self) -> None:
		prices = [_row(item="PMS", segment_no=1)]
		meters = [
			_row(
				item="PMS",
				segment_no=1,
				closing_elec_cash=1000.0,
				closing_elec_meter=None,
				closing_man_meter=None,
			)
		]
		items = _run_gate("_gate_segment_readings", prices=prices, meter_readings=meters)
		self.assertEqual(items, [])

	def test_segment_with_no_reading_fires_S112(self) -> None:
		"""TC-PRC-002: a price segment exists but no closing reading is present → S112."""
		prices = [_row(item="PMS", segment_no=2)]
		meters = [
			_row(
				item="PMS",
				segment_no=1,
				closing_elec_cash=1000.0,
				closing_elec_meter=None,
				closing_man_meter=None,
			)
		]
		items = _run_gate("_gate_segment_readings", prices=prices, meter_readings=meters)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S112")
		self.assertIn("PMS", items[0]["message"])

	def test_segment_reading_with_all_zero_closings_fires_S112(self) -> None:
		"""A reading row where every closing is 0 / None counts as no reading."""
		prices = [_row(item="AGO", segment_no=1)]
		meters = [
			_row(
				item="AGO",
				segment_no=1,
				closing_elec_cash=0.0,
				closing_elec_meter=None,
				closing_man_meter=None,
			)
		]
		items = _run_gate("_gate_segment_readings", prices=prices, meter_readings=meters)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S112")

	def test_no_prices_means_gate_has_nothing_to_check(self) -> None:
		items = _run_gate("_gate_segment_readings", prices=[], meter_readings=[])
		self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# FMS-S113: No draft Fuel Own Use entry may exist in the shift window
# ---------------------------------------------------------------------------


class TestGateNoDraftOwnUse(unittest.TestCase):
	"""FMS-S113: a draft 'Fuel Own Use' Stock Entry inside the shift window blocks close (TC-OWN-002)."""

	def test_no_draft_own_use_entries_passes(self) -> None:
		import frappe

		frappe.get_all.return_value = []
		items = _run_gate(
			"_gate_no_draft_own_use",
			station="STA-001",
			shift_start="2026-10-27 06:00:00",
			shift_end="2026-10-27 18:00:00",
		)
		self.assertEqual(items, [])

	def test_draft_own_use_entry_in_window_fires_S113(self) -> None:
		"""TC-OWN-002: a draft Fuel Own Use entry in the shift window → S113 naming the entry."""
		import frappe

		frappe.get_all.return_value = [
			SimpleNamespace(name="FOU-00001", posting_date="2026-10-27", posting_time="10:00:00"),
		]
		items = _run_gate(
			"_gate_no_draft_own_use",
			station="STA-001",
			shift_start="2026-10-27 06:00:00",
			shift_end="2026-10-27 18:00:00",
		)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S113")
		self.assertIn("FOU-00001", items[0]["message"])


# ---------------------------------------------------------------------------
# FMS-S114: Mobile money and card references must be unique per provider
# ---------------------------------------------------------------------------


class TestGateCollectionRefs(unittest.TestCase):
	"""FMS-S114: duplicate payment references (within the shift or cross-shift) are blocked."""

	def test_all_unique_references_pass(self) -> None:
		import frappe

		frappe.get_all.return_value = []  # no cross-shift duplicates
		collections = [
			_row(collection_type="Mobile Money", provider="MPESA", reference="TX-001", idx=1),
			_row(collection_type="Mobile Money", provider="MPESA", reference="TX-002", idx=2),
		]
		items = _run_gate("_gate_collection_refs", collections=collections)
		self.assertEqual(items, [])

	def test_duplicate_reference_within_same_shift_fires_S114(self) -> None:
		"""Two rows in this shift with the same provider + reference → S114."""
		import frappe

		frappe.get_all.return_value = []
		collections = [
			_row(collection_type="Mobile Money", provider="MPESA", reference="DUPE-999", idx=1),
			_row(collection_type="Mobile Money", provider="MPESA", reference="DUPE-999", idx=2),
		]
		items = _run_gate("_gate_collection_refs", collections=collections)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S114")
		self.assertIn("DUPE-999", items[0]["message"])

	def test_reference_already_used_in_another_shift_fires_S114(self) -> None:
		"""TC-FRD-006: reference used in a previous submitted shift → S114."""
		import frappe

		frappe.get_all.return_value = [
			SimpleNamespace(provider="MPESA", reference="TX-100", parent="SHIFT-PREV"),
		]
		collections = [
			_row(collection_type="Mobile Money", provider="MPESA", reference="TX-100", idx=1),
		]
		items = _run_gate("_gate_collection_refs", collections=collections)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S114")
		self.assertIn("SHIFT-PREV", items[0]["message"])

	def test_missing_reference_on_mobile_money_row_fires_S114(self) -> None:
		"""A mobile money row without a reference is treated as a data problem → S114."""
		import frappe

		frappe.get_all.return_value = []
		collections = [
			_row(collection_type="Mobile Money", provider="MPESA", reference=None, idx=1),
		]
		items = _run_gate("_gate_collection_refs", collections=collections)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S114")

	def test_cash_collections_are_not_checked_for_duplicate_references(self) -> None:
		"""Cash and other non-electronic types are exempt from the reference uniqueness check."""
		import frappe

		frappe.get_all.return_value = []
		collections = [
			_row(collection_type="Cash", provider=None, reference=None, idx=1),
		]
		items = _run_gate("_gate_collection_refs", collections=collections)
		self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# FMS-S116: Shift with pending or rejected approvals cannot be submitted
# ---------------------------------------------------------------------------


class TestGateShiftApproval(unittest.TestCase):
	"""FMS-S116: approval_state Pending Approval or Rejected blocks close."""

	def test_approval_not_required_passes(self) -> None:
		items = _run_gate("_gate_shift_approval", approval_state="Not Required")
		self.assertEqual(items, [])

	def test_already_approved_passes(self) -> None:
		items = _run_gate("_gate_shift_approval", approval_state="Approved")
		self.assertEqual(items, [])

	def test_pending_approval_fires_S116_with_waiting_severity(self) -> None:
		"""TC-APR-001: shift awaiting approval cannot be submitted → S116 severity='waiting'."""
		items = _run_gate("_gate_shift_approval", approval_state="Pending Approval")
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S116")
		self.assertEqual(items[0]["severity"], "waiting")

	def test_rejected_approval_fires_S116(self) -> None:
		"""TC-APR-007: a rejected shift must be re-approved before close → S116."""
		items = _run_gate("_gate_shift_approval", approval_state="Rejected")
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-S116")


# ---------------------------------------------------------------------------
# FMS-W103: Drift beyond tolerance — reason required
# ---------------------------------------------------------------------------


class TestGateDriftReason(unittest.TestCase):
	"""FMS-W103: when settings require a reason, a drift_breach flag without a reason blocks close (TC-MTR-010)."""

	def _mock_settings(self, drift_requires_reason: bool) -> None:
		import frappe

		frappe.get_cached_doc.return_value = SimpleNamespace(drift_requires_reason=drift_requires_reason)

	def test_no_breach_rows_passes(self) -> None:
		self._mock_settings(drift_requires_reason=True)
		rows = [_row(nozzle="N1", drift_breach=0, drift_reason=None)]
		items = _run_gate("_gate_drift_reason", meter_readings=rows)
		self.assertEqual(items, [])

	def test_breach_with_reason_passes(self) -> None:
		self._mock_settings(drift_requires_reason=True)
		rows = [_row(nozzle="N1", drift_breach=1, drift_reason="Meter calibration")]
		items = _run_gate("_gate_drift_reason", meter_readings=rows)
		self.assertEqual(items, [])

	def test_breach_without_reason_fires_W103(self) -> None:
		"""TC-MTR-010: drift_breach set but no drift_reason → W103 naming the nozzle."""
		self._mock_settings(drift_requires_reason=True)
		rows = [_row(nozzle="N1", drift_breach=1, drift_reason=None)]
		items = _run_gate("_gate_drift_reason", meter_readings=rows)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["code"], "FMS-W103")
		self.assertIn("N1", items[0]["message"])

	def test_drift_requires_reason_disabled_means_gate_skipped(self) -> None:
		"""TC-MTR-011: when station is set to Warn, drift does not block close."""
		self._mock_settings(drift_requires_reason=False)
		rows = [_row(nozzle="N1", drift_breach=1, drift_reason=None)]
		items = _run_gate("_gate_drift_reason", meter_readings=rows)
		self.assertEqual(items, [])

	def test_multiple_breach_nozzles_listed_in_one_W103_item(self) -> None:
		self._mock_settings(drift_requires_reason=True)
		rows = [
			_row(nozzle="N1", drift_breach=1, drift_reason=None),
			_row(nozzle="N2", drift_breach=1, drift_reason=None),
		]
		items = _run_gate("_gate_drift_reason", meter_readings=rows)
		self.assertEqual(len(items), 1)
		self.assertIn("N1", items[0]["message"])
		self.assertIn("N2", items[0]["message"])


# ---------------------------------------------------------------------------
# Gate collection: all blocking gates together
# ---------------------------------------------------------------------------


class TestAllGatesRunTogether(unittest.TestCase):
	"""GTE-004: before_submit collects items from every gate in one pass; none are skipped."""

	def test_shift_with_three_problems_produces_three_separate_items(self) -> None:
		"""Three different gates fire independently; every item has a unique code."""
		import frappe

		frappe.get_all.return_value = []
		frappe.db.get_value.return_value = None

		ForecourtShift = _import_shift()
		doc = _make_shift(
			meter_readings=[
				_row(
					nozzle="N1",
					rec_elec_cash=1,
					closing_elec_cash=100.0,
					opening_elec_cash=900.0,
					rollover_elec_cash=0,
					rec_elec_meter=0,
					rec_man_meter=0,
					cashier=None,
					item=None,
					segment_no=None,
				),
			],
			cashiers=[_row(cashier="EMP-001", difference=-100.0, resolved=0)],
			prices=[_row(item="PMS", segment_no=1)],
		)
		items: list[dict] = []
		ForecourtShift._gate_nozzle_readings(doc, items)
		ForecourtShift._gate_nozzle_cashier(doc, items)
		ForecourtShift._gate_cashier_resolved(doc, items)
		ForecourtShift._gate_segment_readings(doc, items)

		codes = {item["code"] for item in items}
		self.assertIn("FMS-S101", codes)
		self.assertIn("FMS-S104", codes)
		self.assertIn("FMS-S105", codes)
		self.assertIn("FMS-S112", codes)

	def test_severity_field_is_always_one_of_the_three_valid_values(self) -> None:
		"""GTE-005: every gate item must have severity 'blocking', 'waiting', or 'attention'."""
		import frappe

		frappe.db.get_value.return_value = None
		frappe.get_all.return_value = []
		frappe.get_cached_doc.return_value = SimpleNamespace(drift_requires_reason=True)

		ForecourtShift = _import_shift()
		doc = _make_shift(
			approval_state="Pending Approval",
			cashiers=[_row(cashier="A", difference=-50.0, resolved=0)],
			meter_readings=[_row(nozzle="N1", drift_breach=1, drift_reason=None)],
		)
		items: list[dict] = []
		ForecourtShift._gate_cashier_resolved(doc, items)
		ForecourtShift._gate_shift_approval(doc, items)
		ForecourtShift._gate_drift_reason(doc, items)

		valid = {"blocking", "waiting", "attention"}
		for item in items:
			self.assertIn(item["severity"], valid, msg=f"Unexpected severity in item: {item}")


if __name__ == "__main__":
	unittest.main()
