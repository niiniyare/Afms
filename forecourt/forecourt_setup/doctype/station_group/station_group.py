from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet

from forecourt.errors import FMS_M630


class StationGroup(NestedSet):
	nsm_parent_field = "parent_station_group"

	def validate(self) -> None:
		if not self.is_group and frappe.db.exists(
			"Station Group",
			{"parent_station_group": self.name},
		):
			frappe.throw(
				_("{0}: Cannot unset Is Group because this Station Group has children.").format(FMS_M630),
				frappe.ValidationError,
			)

	def on_update(self) -> None:
		super().on_update()


def has_permission(doc: "frappe.Document", ptype: str, user: str) -> bool | None:
	"""Expand a User Permission on a Station Group to include all descendants."""
	if ptype not in ("read", "select"):
		return None

	permitted_groups = frappe.permissions.get_user_permissions(user).get("Station Group", [])
	if not permitted_groups:
		return None

	permitted_names = {p.get("doc") for p in permitted_groups}
	if doc.name in permitted_names:
		return True

	# True if doc is a descendant of any permitted group
	for group_name in permitted_names:
		root = frappe.db.get_value("Station Group", group_name, ["lft", "rgt"], as_dict=True)
		if not root:
			continue
		node = frappe.db.get_value("Station Group", doc.name, ["lft", "rgt"], as_dict=True)
		if not node:
			continue
		if root.lft < node.lft and node.rgt < root.rgt:
			return True

	return None


def permission_query_conditions(user: str) -> str:
	"""Restrict list view to groups the user has permission on (and their descendants)."""
	permitted_groups = frappe.permissions.get_user_permissions(user).get("Station Group", [])
	if not permitted_groups:
		return ""

	clauses: list[str] = []
	for p in permitted_groups:
		root = frappe.db.get_value("Station Group", p.get("doc"), ["lft", "rgt"], as_dict=True)
		if not root:
			continue
		clauses.append(f"(`tabStation Group`.`lft` >= {root.lft} AND `tabStation Group`.`rgt` <= {root.rgt})")

	if not clauses:
		return ""

	return "(" + " OR ".join(clauses) + ")"
