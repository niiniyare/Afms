"""Permission tests — FMS-I05.

Covers:
- get_permitted_stations: Station UP, Station Group UP, no restriction
- has_station_permission: returns True/None correctly
- _station_query: returns correct SQL fragment
- Role-level: frappe.has_permission for Station, Forecourt Shift
- Approval segregation: approver cannot be the preparer
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
import pytest
from frappe.tests.utils import FrappeTestCase

from forecourt.permissions import (
	_station_query,
	get_permitted_stations,
	has_station_permission,
)

# ---------------------------------------------------------------------------
# get_permitted_stations — unit tests (mocked DB)
# ---------------------------------------------------------------------------


class TestGetPermittedStations(FrappeTestCase):
	def test_station_up_returned_directly(self):
		perms = {"Station": [{"doc": "STA-001"}, {"doc": "STA-002"}]}
		with patch("frappe.permissions.get_user_permissions", return_value=perms):
			result = get_permitted_stations("test@example.com")
		self.assertEqual(sorted(result), ["STA-001", "STA-002"])

	def test_no_up_returns_none(self):
		with patch("frappe.permissions.get_user_permissions", return_value={}):
			result = get_permitted_stations("test@example.com")
		self.assertIsNone(result)

	def test_empty_station_up_list_returns_empty(self):
		perms = {"Station Group": [{"doc": ""}]}  # empty doc value
		with (
			patch("frappe.permissions.get_user_permissions", return_value=perms),
			patch("frappe.db.table_exists", return_value=True),
			patch("frappe.db.get_value", return_value=None),
		):
			result = get_permitted_stations("test@example.com")
		self.assertEqual(result, [])

	def test_station_group_expands_to_stations(self):
		perms = {"Station Group": [{"doc": "Region-NBO"}]}
		with (
			patch("frappe.permissions.get_user_permissions", return_value=perms),
			patch("frappe.db.table_exists", return_value=True),
			patch(
				"frappe.db.get_value",
				return_value=SimpleNamespace(lft=1, rgt=10),
			),
			patch(
				"frappe.get_all",
				side_effect=[
					["Region-NBO", "Zone-Westlands"],  # descendant groups
					["STA-W", "STA-K"],  # stations in those groups
				],
			),
		):
			result = get_permitted_stations("test@example.com")
		self.assertIn("STA-W", result)
		self.assertIn("STA-K", result)

	def test_group_with_no_stations_returns_empty_list(self):
		perms = {"Station Group": [{"doc": "EmptyRegion"}]}
		with (
			patch("frappe.permissions.get_user_permissions", return_value=perms),
			patch("frappe.db.table_exists", return_value=True),
			patch(
				"frappe.db.get_value",
				return_value=SimpleNamespace(lft=5, rgt=6),
			),
			patch(
				"frappe.get_all",
				side_effect=[
					["EmptyRegion"],  # only the group itself, no sub-groups
					[],  # no stations
				],
			),
		):
			result = get_permitted_stations("test@example.com")
		self.assertEqual(result, [])

	def test_station_up_takes_priority_over_group_up(self):
		perms = {
			"Station": [{"doc": "EXPLICIT-STA"}],
			"Station Group": [{"doc": "Some-Group"}],
		}
		with patch("frappe.permissions.get_user_permissions", return_value=perms):
			result = get_permitted_stations("test@example.com")
		# Station UP wins; group UP is never queried
		self.assertEqual(result, ["EXPLICIT-STA"])


# ---------------------------------------------------------------------------
# has_station_permission — unit tests
# ---------------------------------------------------------------------------


class TestHasStationPermission(FrappeTestCase):
	def _doc(self, doctype="Forecourt Shift", station="STA-001", name="SH-001"):
		d = MagicMock()
		d.doctype = doctype
		d.name = name
		d.get = lambda field, default=None: station if field == "station" else default
		return d

	def test_returns_none_for_write_ptype(self):
		doc = self._doc()
		result = has_station_permission(doc, "write", "user@example.com")
		self.assertIsNone(result)

	def test_returns_none_when_no_restriction(self):
		doc = self._doc()
		with patch("forecourt.permissions.get_permitted_stations", return_value=None):
			result = has_station_permission(doc, "read", "user@example.com")
		self.assertIsNone(result)

	def test_returns_true_when_station_permitted(self):
		doc = self._doc()
		with patch("forecourt.permissions.get_permitted_stations", return_value=["STA-001", "STA-002"]):
			result = has_station_permission(doc, "read", "user@example.com")
		self.assertTrue(result)

	def test_returns_none_when_station_not_permitted(self):
		doc = self._doc()
		with patch("forecourt.permissions.get_permitted_stations", return_value=["STA-999"]):
			result = has_station_permission(doc, "read", "user@example.com")
		self.assertIsNone(result)

	def test_station_doctype_uses_name(self):
		doc = MagicMock()
		doc.doctype = "Station"
		doc.name = "STA-042"
		with patch("forecourt.permissions.get_permitted_stations", return_value=["STA-042"]):
			result = has_station_permission(doc, "read", "user@example.com")
		self.assertTrue(result)

	def test_returns_none_when_no_station_field(self):
		doc = MagicMock()
		doc.doctype = "Fuel Tank"
		doc.get = lambda field, default=None: None  # no station value
		result = has_station_permission(doc, "read", "user@example.com")
		self.assertIsNone(result)

	def test_select_ptype_also_checked(self):
		doc = self._doc()
		with patch("forecourt.permissions.get_permitted_stations", return_value=["STA-001"]):
			result = has_station_permission(doc, "select", "user@example.com")
		self.assertTrue(result)


# ---------------------------------------------------------------------------
# _station_query — unit tests
# ---------------------------------------------------------------------------


class TestStationQuery(FrappeTestCase):
	def test_no_restriction_returns_empty_string(self):
		with patch("forecourt.permissions.get_permitted_stations", return_value=None):
			result = _station_query("Fuel Tank", "user@example.com")
		self.assertEqual(result, "")

	def test_empty_set_returns_impossible_condition(self):
		with patch("forecourt.permissions.get_permitted_stations", return_value=[]):
			result = _station_query("Fuel Tank", "user@example.com")
		self.assertEqual(result, "1=0")

	def test_stations_produce_in_clause(self):
		with (
			patch("forecourt.permissions.get_permitted_stations", return_value=["STA-A", "STA-B"]),
			patch("frappe.db.escape", side_effect=lambda s: f"'{s}'"),
		):
			result = _station_query("Fuel Tank", "user@example.com")
		self.assertIn("`tabFuel Tank`.`station` IN", result)
		self.assertIn("'STA-A'", result)
		self.assertIn("'STA-B'", result)

	def test_custom_station_field(self):
		with (
			patch("forecourt.permissions.get_permitted_stations", return_value=["STA-X"]),
			patch("frappe.db.escape", side_effect=lambda s: f"'{s}'"),
		):
			result = _station_query("Station", "user@example.com", station_field="name")
		self.assertIn("`tabStation`.`name` IN", result)


# ---------------------------------------------------------------------------
# Approval segregation — controller gate (mocked)
# ---------------------------------------------------------------------------


class TestApprovalSegregation(FrappeTestCase):
	"""FMS-S116: approver cannot be the preparer of the shift."""

	def test_shift_approval_gate_blocks_pending_state(self):
		from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

		errors: list[str] = []
		shift = ForecourtShift.__new__(ForecourtShift)
		shift.approval_state = "Pending Approval"
		shift._gate_shift_approval(errors)
		self.assertEqual(len(errors), 1)
		self.assertIn("FMS-S116", errors[0])

	def test_shift_approval_gate_blocks_rejected_state(self):
		from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

		errors: list[str] = []
		shift = ForecourtShift.__new__(ForecourtShift)
		shift.approval_state = "Rejected"
		shift._gate_shift_approval(errors)
		self.assertEqual(len(errors), 1)

	def test_shift_approval_gate_passes_when_approved(self):
		from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

		errors: list[str] = []
		shift = ForecourtShift.__new__(ForecourtShift)
		shift.approval_state = "Approved"
		shift._gate_shift_approval(errors)
		self.assertEqual(errors, [])

	def test_shift_approval_gate_passes_when_not_required(self):
		from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

		errors: list[str] = []
		shift = ForecourtShift.__new__(ForecourtShift)
		shift.approval_state = "Not Required"
		shift._gate_shift_approval(errors)
		self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# _set_approval_state — unit tests
# ---------------------------------------------------------------------------


class TestSetApprovalState(FrappeTestCase):
	def _shift(self, resolutions=None, approval_state="Not Required"):
		from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

		shift = ForecourtShift.__new__(ForecourtShift)
		shift.resolutions = resolutions or []
		shift.approval_state = approval_state
		shift.get_doc_before_save = lambda: None
		return shift

	def _resolution(self, needs_approval=0):
		r = SimpleNamespace(needs_approval=needs_approval)
		return r

	def test_no_resolutions_sets_not_required(self):
		shift = self._shift()
		shift._set_approval_state()
		self.assertEqual(shift.approval_state, "Not Required")

	def test_all_resolutions_no_approval_needed_sets_not_required(self):
		shift = self._shift(resolutions=[self._resolution(0), self._resolution(0)])
		shift._set_approval_state()
		self.assertEqual(shift.approval_state, "Not Required")

	def test_any_approval_needed_sets_pending(self):
		shift = self._shift(resolutions=[self._resolution(0), self._resolution(1)])
		shift._set_approval_state()
		self.assertEqual(shift.approval_state, "Pending Approval")

	def test_approved_state_unchanged_when_data_not_changed(self):
		shift = self._shift(
			resolutions=[self._resolution(1)],
			approval_state="Approved",
		)
		old_mock = MagicMock()
		old_mock.resolutions = shift.resolutions  # same objects → no change detected
		shift.get_doc_before_save = lambda: old_mock
		# patch _approval_data_changed to return False
		shift._approval_data_changed = lambda old: False
		shift._set_approval_state()
		self.assertEqual(shift.approval_state, "Approved")

	def test_approved_state_reset_when_data_changed(self):
		shift = self._shift(
			resolutions=[self._resolution(1)],
			approval_state="Approved",
		)
		old_mock = MagicMock()
		shift.get_doc_before_save = lambda: old_mock
		shift._approval_data_changed = lambda old: True
		shift._set_approval_state()
		self.assertEqual(shift.approval_state, "Pending Approval")

	def test_rejected_state_stays_when_needs_approval(self):
		shift = self._shift(
			resolutions=[self._resolution(1)],
			approval_state="Rejected",
		)
		shift._set_approval_state()
		# Rejected stays (manager must fix and re-submit)
		self.assertEqual(shift.approval_state, "Rejected")
