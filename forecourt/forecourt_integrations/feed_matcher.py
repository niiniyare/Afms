"""Payment Feed Entry ↔ Forecourt Shift matcher — FMS-J04.

Called:
  - from Forecourt Shift after_insert (to pick up feeds for the new window)
  - from a Refresh button on the shift form
  - from before_submit to gate on unassigned feeds (FMS-S111)

Logic:
  For each Unmatched feed entry where station matches and
  transaction_time falls within [shift_start, shift_end]:
    1. Find the cashier for the feed entry's till (same till_to_cashier
       logic as statement_import, using the provider's import_mapping).
    2. If the reference already exists in shift.collections → skip.
    3. Otherwise append a Shift Collection row and mark the feed as Matched.

Gate FMS-S111: before_submit, if any Unmatched feed entry exists for the
station within the shift window, raise an error.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_datetime

from forecourt.errors import FMS_S111, FMSValidationError
from forecourt.forecourt_integrations.statement_import import (
	_collection_type_for_provider,
	_load_mapping,
	_resolve_cashier,
)


def match_feeds_to_shift(shift_doc: "frappe.Document") -> int:
	"""Pull Unmatched feed entries into shift.collections.

	Returns the count of newly created collection rows.
	"""
	if not shift_doc.station or not shift_doc.shift_start or not shift_doc.shift_end:
		return 0

	shift_start = get_datetime(shift_doc.shift_start)
	shift_end = get_datetime(shift_doc.shift_end)

	feeds = frappe.get_list(
		"Payment Feed Entry",
		filters={
			"station": shift_doc.station,
			"status": "Unmatched",
			"transaction_time": ["between", [shift_start, shift_end]],
		},
		fields=["name", "provider", "till_or_terminal", "reference", "amount", "payer", "transaction_time"],
	)

	if not feeds:
		return 0

	existing_refs: set[str] = {r.reference for r in shift_doc.collections if r.reference}
	cashier_list: list[str] = [c.cashier for c in shift_doc.cashiers if c.cashier]
	created = 0

	for feed in feeds:
		if feed.reference in existing_refs:
			frappe.db.set_value(
				"Payment Feed Entry",
				feed.name,
				{"status": "Matched", "forecourt_shift": shift_doc.name},
				update_modified=False,
			)
			continue

		provider_doc = frappe.get_cached_doc("Payment Provider", feed.provider)
		mapping = _load_mapping(provider_doc)
		till_map: dict[str, str] = mapping.get("till_to_cashier") or {}
		default_cashier: str = mapping.get("default_cashier") or ""

		cashier = _resolve_cashier(
			till=feed.till_or_terminal or "",
			till_map=till_map,
			default_cashier=default_cashier,
			cashier_list=cashier_list,
		)
		if not cashier:
			continue

		collection_type = _collection_type_for_provider(provider_doc)
		shift_doc.append(
			"collections",
			{
				"cashier": cashier,
				"collection_type": collection_type,
				"provider": feed.provider,
				"reference": feed.reference,
				"amount": flt(feed.amount, 2),
				"till_or_terminal": feed.till_or_terminal or "",
				"payer": feed.payer or "",
				"transaction_time": feed.transaction_time or None,
				"feed_entry": feed.name,
			},
		)
		existing_refs.add(feed.reference)
		frappe.db.set_value(
			"Payment Feed Entry",
			feed.name,
			{"status": "Matched", "forecourt_shift": shift_doc.name},
			update_modified=False,
		)
		created += 1

	return created


def gate_unmatched_feeds(shift_doc: "frappe.Document") -> None:
	"""Raise FMS-S111 if any Unmatched feed entry exists in the shift window."""
	if not shift_doc.station or not shift_doc.shift_start or not shift_doc.shift_end:
		return

	shift_start = get_datetime(shift_doc.shift_start)
	shift_end = get_datetime(shift_doc.shift_end)

	unmatched = frappe.db.count(
		"Payment Feed Entry",
		{
			"station": shift_doc.station,
			"status": "Unmatched",
			"transaction_time": ["between", [shift_start, shift_end]],
		},
	)
	if unmatched:
		raise FMSValidationError(
			FMS_S111,
			_(
				"{0}: {1} payment feed entries for this shift have not been assigned to a cashier. "
				"Assign or ignore them before closing."
			).format(FMS_S111, unmatched),
		)
