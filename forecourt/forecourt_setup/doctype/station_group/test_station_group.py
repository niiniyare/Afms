from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


def _root() -> str:
	return "All Station Groups"


def _make(
	name: str, parent: str = _root(), group_type: str = "Region", is_group: int = 0
) -> "frappe.Document":
	if frappe.db.exists("Station Group", name):
		return frappe.get_doc("Station Group", name)
	doc = frappe.get_doc(
		{
			"doctype": "Station Group",
			"station_group_name": name,
			"group_type": group_type,
			"parent_station_group": parent,
			"is_group": is_group,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


class TestStationGroup(FrappeTestCase):
	def setUp(self) -> None:
		frappe.db.delete("Station Group", {"station_group_name": ["like", "_test_%"]})

	def tearDown(self) -> None:
		frappe.db.delete("Station Group", {"station_group_name": ["like", "_test_%"]})

	def test_root_fixture_exists(self) -> None:
		self.assertTrue(
			frappe.db.exists("Station Group", _root()),
			"Root fixture 'All Station Groups' not found — run bench migrate to sync fixtures.",
		)

	def test_insert_child(self) -> None:
		doc = _make("_test_Region_East")
		self.assertEqual(doc.parent_station_group, _root())

	def test_tree_order(self) -> None:
		parent = _make("_test_Brand_A", is_group=1)
		child = _make("_test_Area_A1", parent=parent.name)
		parent.reload()
		child.reload()
		self.assertGreater(child.lft, parent.lft)
		self.assertLess(child.rgt, parent.rgt)

	def test_unset_is_group_refused_when_has_children(self) -> None:
		parent = _make("_test_Brand_B", is_group=1)
		_make("_test_Area_B1", parent=parent.name)
		parent.reload()
		parent.is_group = 0
		with self.assertRaisesRegex(frappe.ValidationError, "FMS-M630"):
			parent.save()
