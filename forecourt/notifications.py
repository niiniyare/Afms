"""FMS approval notification helpers — FMS-I04.

Called from on_update on Forecourt Shift, Shift Correction, and
Fuel Price Change when the approval/workflow state transitions to a
state that requires human action.

Sends both an email (queued) and a real-time system notification.
Recipients: all active users with the required role.  Station-level
filtering is omitted here — the station is included in the subject so
the right approver acts.  Role-based User Permission filtering can be
added in a later iteration.
"""

from __future__ import annotations

import frappe
from frappe import _


def on_forecourt_shift_update(doc: "frappe.Document", method: str | None = None) -> None:
	"""Notify area managers when a shift enters Pending Approval."""
	if doc.approval_state != "Pending Approval":
		return
	old = doc.get_doc_before_save()
	if old and getattr(old, "approval_state", None) == "Pending Approval":
		return
	subject = _("[FMS] Shift {0} at {1} awaits approval").format(doc.name, doc.station)
	message = _(
		"Shift {0} at station {1} has write-offs or tank variances that require your approval "
		"before it can be closed. Please review and approve or reject."
	).format(doc.name, doc.station)
	_notify(
		subject=subject,
		message=message,
		roles=["Area Manager"],
		reference_doctype="Forecourt Shift",
		reference_name=doc.name,
		exclude_user=doc.owner,
	)


def on_shift_correction_update(doc: "frappe.Document", method: str | None = None) -> None:
	"""Notify Forecourt Directors when a correction enters Pending Director Approval."""
	if doc.workflow_state != "Pending Director Approval":
		return
	old = doc.get_doc_before_save()
	if old and getattr(old, "workflow_state", None) == "Pending Director Approval":
		return
	subject = _("[FMS] Shift Correction {0} awaits director approval").format(doc.name)
	message = _(
		"Shift Correction {0} for shift {1} has been submitted and requires director approval."
	).format(doc.name, doc.forecourt_shift)
	_notify(
		subject=subject,
		message=message,
		roles=["Forecourt Director"],
		reference_doctype="Shift Correction",
		reference_name=doc.name,
	)


def on_fuel_price_change_update(doc: "frappe.Document", method: str | None = None) -> None:
	"""Notify area managers when a fuel price change enters Pending Approval."""
	if doc.approval_state != "Pending Approval":
		return
	old = doc.get_doc_before_save()
	if old and getattr(old, "approval_state", None) == "Pending Approval":
		return
	subject = _("[FMS] Fuel Price Change {0} at {1} awaits approval").format(doc.name, doc.station)
	message = _(
		"A fuel price change for station {0} has been submitted and requires your approval "
		"before it takes effect."
	).format(doc.station)
	_notify(
		subject=subject,
		message=message,
		roles=["Area Manager"],
		reference_doctype="Fuel Price Change",
		reference_name=doc.name,
	)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _notify(
	subject: str,
	message: str,
	roles: list[str],
	reference_doctype: str,
	reference_name: str,
	exclude_user: str | None = None,
) -> None:
	recipients = _get_role_users(roles, exclude_user)
	if not recipients:
		return
	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=f"<p>{message}</p>",
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		delayed=True,
	)
	for user in recipients:
		frappe.publish_realtime(
			event="msgprint",
			message={"msg": message, "title": subject},
			user=user,
			after_commit=True,
		)


def _get_role_users(roles: list[str], exclude_user: str | None = None) -> list[str]:
	users: set[str] = set()
	for role in roles:
		for u in frappe.get_all(
			"Has Role",
			filters={"role": role, "parenttype": "User"},
			pluck="parent",
		):
			if u and u != "Administrator":
				users.add(u)
	if exclude_user:
		users.discard(exclude_user)
	if not users:
		return []
	active = frappe.get_all(
		"User",
		filters={"name": ["in", list(users)], "enabled": 1},
		pluck="email",
	)
	return [e for e in active if e]
