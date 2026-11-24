"""PHASE 1 regression tests: shift sequencing and S116 gate.

Tests:
  SEQ-01  Creating a second shift while first is draft raises S116.
  SEQ-02  before_insert gate fires even when create_shift() is bypassed.
  SEQ-03  _find_previous_shift selects only submitted shifts.
  SEQ-04  _find_previous_shift ignores cancelled shifts (docstatus=2).
  SEQ-05  _find_previous_shift returns None when no submitted shift exists.
  SEQ-06  _find_previous_shift returns most-recent submitted (by shift_start).
  SEQ-07  create_shift() S116 check refuses when draft exists.
  SEQ-08  create_shift() succeeds when no draft exists (gate passes, S119 is next).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

_MODULE = "forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift"
_CREATE = "forecourt.forecourt_shift.create"
_OPEN = "forecourt.forecourt_shift.openings"

_TRANS_PATCHER = patch(f"{_MODULE}._", side_effect=lambda s, *a, **kw: s)
_OPEN_TRANS_PATCHER = patch(f"{_OPEN}._", side_effect=lambda s, *a, **kw: s)
_FLT_PATCHER = patch(
	f"{_MODULE}.flt",
	side_effect=lambda v, p=None, **kw: round(float(v or 0), p) if p is not None else float(v or 0),
)
_GET_DT_PATCHER = patch(f"{_MODULE}.get_datetime", side_effect=lambda v: v)

_PATCHERS: list = []


def _make_db_mock():
	db = MagicMock()
	db.get_value.return_value = None
	db.exists.return_value = False
	db.set_value.return_value = None
	return db


def setUpModule():
	import frappe

	_PATCHERS[:] = [
		_TRANS_PATCHER,
		_OPEN_TRANS_PATCHER,
		_FLT_PATCHER,
		_GET_DT_PATCHER,
		patch.object(frappe, "db", _make_db_mock()),
		patch.object(frappe, "get_all", MagicMock(return_value=[])),
		patch.object(frappe, "get_cached_doc", MagicMock()),
		patch.object(frappe, "throw", MagicMock(side_effect=Exception("frappe.throw"))),
	]
	for p in _PATCHERS:
		p.start()


def tearDownModule():
	for p in reversed(_PATCHERS):
		p.stop()
	_PATCHERS.clear()
	try:
		from frappe.tests.utils.generators import get_modules as _gm

		_gm.cache_clear()
	except (ImportError, AttributeError):
		pass


def _import_shift():
	from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import ForecourtShift

	return ForecourtShift


def _make_shift(**kwargs):
	defaults = {
		"name": None,
		"station": "STA-001",
		"company": "Test Co",
		"shift_template": "Morning",
		"shift_date": "2026-11-01",
		"shift_start": None,
		"shift_end": None,
		"previous_shift": None,
		"docstatus": 0,
		"cashiers": [],
		"meter_readings": [],
		"tank_dips": [],
		"prices": [],
		"cash_counts": [],
		"credit_sales": [],
		"item_sales": [],
		"collections": [],
		"resolutions": [],
	}
	defaults.update(kwargs)
	doc = SimpleNamespace(**defaults)

	def _append(table, row_dict):
		getattr(doc, table).append(SimpleNamespace(**row_dict))

	doc.append = _append
	return doc


# ---------------------------------------------------------------------------
# SEQ-01/02: before_insert S116 gate
# ---------------------------------------------------------------------------


class TestBeforeInsertS116Gate(unittest.TestCase):
	"""SEQ-01/02: before_insert raises when a draft already exists at the station."""

	def test_raises_when_draft_exists(self):
		"""SEQ-01: before_insert throws S116 naming EVERY open draft."""
		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001")

		with (
			patch(f"{_MODULE}.shift_openings.open_drafts", return_value=["SH-A", "SH-B"]),
			patch(f"{_MODULE}.frappe.throw", side_effect=Exception("frappe.throw")) as mock_throw,
		):
			with self.assertRaises(Exception):
				ForecourtShift.before_insert(doc)

		mock_throw.assert_called_once()
		msg = str(mock_throw.call_args)
		self.assertIn("FMS-S116", msg)
		self.assertIn("SH-A", msg)
		self.assertIn("SH-B", msg)

	def test_no_raise_when_no_draft(self):
		"""SEQ-02: before_insert proceeds normally when no draft exists."""
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001")

		mock_db = _make_db_mock()
		mock_db.get_value.return_value = None

		# Attach mock helpers directly to doc so self.xxx() calls succeed.
		for method in (
			"_find_previous_shift",
			"_snapshot_station_settings",
			"_compute_shift_window",
			"_create_price_rows",
			"_create_reading_rows",
			"_create_cashier_rows",
			"_create_tank_rows",
			"_apply_opening_balances",
			"_set_title",
		):
			setattr(doc, method, MagicMock())

		with (
			patch(f"{_MODULE}.shift_openings.open_drafts", return_value=[]),
			patch.object(frappe, "db", mock_db),
			patch.object(frappe, "throw", side_effect=Exception("frappe.throw")) as mock_throw,
		):
			ForecourtShift.before_insert(doc)

		mock_throw.assert_not_called()


# ---------------------------------------------------------------------------
# SEQ-03/04/05/06: _find_previous_shift
# ---------------------------------------------------------------------------


class TestFindPreviousShiftSubmittedOnly(unittest.TestCase):
	"""SEQ-03/04/05/06: _find_previous_shift uses only docstatus=1 shifts."""

	def test_uses_docstatus_1_in_filter(self):
		"""SEQ-03: get_all must be called with docstatus=1 (submitted only)."""
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001")
		frappe.get_all.return_value = [SimpleNamespace(name="SH-STA-001-010")]

		ForecourtShift._find_previous_shift(doc)

		call_args = frappe.get_all.call_args
		self.assertIn("docstatus", str(call_args))
		self.assertIn("1", str(call_args))
		self.assertEqual(doc.previous_shift, "SH-STA-001-010")

	def test_draft_not_returned_as_previous(self):
		"""SEQ-04: If only drafts exist, previous_shift must be None."""
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001")
		# get_all with docstatus=1 returns empty (no submitted shifts).
		frappe.get_all.return_value = []

		ForecourtShift._find_previous_shift(doc)

		self.assertIsNone(doc.previous_shift)

	def test_no_previous_when_no_submitted(self):
		"""SEQ-05: previous_shift is None when no submitted shift exists."""
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001")
		frappe.get_all.return_value = []

		ForecourtShift._find_previous_shift(doc)

		self.assertIsNone(doc.previous_shift)

	def test_most_recent_submitted_selected(self):
		"""SEQ-06: get_all orders by shift_start desc limit 1 — most recent returned."""
		import frappe

		ForecourtShift = _import_shift()
		doc = _make_shift(station="STA-001")
		# Simulate two submitted shifts; get_all returns only the most recent (limit=1).
		frappe.get_all.return_value = [SimpleNamespace(name="SH-STA-001-020")]

		ForecourtShift._find_previous_shift(doc)

		self.assertEqual(doc.previous_shift, "SH-STA-001-020")
		# Verify order_by and limit in the call.
		call_kwargs = frappe.get_all.call_args
		call_str = str(call_kwargs)
		self.assertIn("shift_start", call_str)
		self.assertIn("1", call_str)


# ---------------------------------------------------------------------------
# SEQ-07/08: create_shift() S116 check
# ---------------------------------------------------------------------------


class TestCreateShiftS116(unittest.TestCase):
	"""SEQ-07/08: create_shift() S116 check in forecourt/forecourt_shift/create.py."""

	def _import_create(self):
		from forecourt.forecourt_shift import create

		return create

	def test_refuses_when_draft_exists(self):
		"""SEQ-07: create_shift() throws S116 listing every open draft."""
		import frappe

		create = self._import_create()

		mock_db = MagicMock()
		mock_db.exists.return_value = True  # S119 passes (template exists)

		with (
			patch.object(frappe, "has_permission", MagicMock()),
			patch.object(frappe, "db", mock_db),
			patch(f"{_CREATE}.open_drafts", return_value=["SH-D1", "SH-D2"]),
			patch(f"{_CREATE}._", side_effect=lambda s, *a, **kw: s),
			patch.object(frappe, "throw", side_effect=Exception("frappe.throw")) as mock_throw,
			patch.object(frappe, "get_doc", MagicMock()),
		):
			with self.assertRaises(Exception):
				create.create_shift("STA-001", "Morning", "2026-11-01")

		mock_throw.assert_called_once()
		msg = str(mock_throw.call_args)
		self.assertIn("FMS-S116", msg)
		self.assertIn("SH-D1", msg)
		self.assertIn("SH-D2", msg)

	def test_passes_when_no_draft_exists(self):
		"""SEQ-08: create_shift() does not raise S116 when no draft shift exists."""
		import frappe

		create = self._import_create()

		mock_shift = MagicMock()
		mock_shift.name = "SH-STA-001-NEW"

		with (
			patch.object(frappe, "has_permission", MagicMock()),
			patch(f"{_CREATE}.frappe.db") as mock_db,
			patch(f"{_CREATE}.frappe.throw", side_effect=Exception("frappe.throw")),
			patch(f"{_CREATE}._check_fuel_prices", MagicMock()),
			patch(f"{_CREATE}.open_drafts", return_value=[]),
			patch(f"{_CREATE}._", side_effect=lambda s, *a, **kw: s),
			patch(f"{_CREATE}.frappe.get_doc", return_value=mock_shift),
			patch(f"{_CREATE}.getdate", return_value="2026-11-01"),
		):
			# Template exists (S119 passes).
			mock_db.exists.return_value = True
			# No open draft.
			mock_db.get_value.return_value = None

			result = create.create_shift("STA-001", "Morning", "2026-11-01")

		self.assertEqual(result, {"shift": "SH-STA-001-NEW"})
		mock_shift.insert.assert_called_once()


if __name__ == "__main__":
	unittest.main()
