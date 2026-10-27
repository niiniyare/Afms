"""Statement import — FMS-J01.

Parses a CSV or Excel statement file attached to a Payment Import Batch and
creates Shift Collection rows on the target Forecourt Shift, skipping
duplicates by reference.

Import mapping JSON format (set on Payment Provider.import_mapping):
{
  "reference": "<column header>",       # required
  "amount":    "<column header>",       # required
  "till":      "<column header>",       # optional; used to assign cashier
  "payer":     "<column header>",       # optional
  "transaction_time": "<column header>",# optional
  "till_to_cashier": {                  # optional; till value → Employee name
    "T001": "HR-EMP-00001"
  },
  "default_cashier": "<Employee name>"  # fallback when till not matched
}
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

# ---------------------------------------------------------------------------
# Public whitelisted entry points
# ---------------------------------------------------------------------------


@frappe.whitelist()
def run(batch: str) -> dict:
	"""Parse statement file and create Shift Collection rows.

	Called from the Payment Import Batch form (Run Import button) and from
	run_for_shift().  Updates rows_read / rows_created / rows_duplicate /
	rows_rejected / log on the batch doc.

	Returns a summary dict for display.
	"""
	batch_doc = frappe.get_doc("Payment Import Batch", batch)
	frappe.has_permission("Payment Import Batch", "write", batch_doc, throw=True)

	if not batch_doc.forecourt_shift:
		frappe.throw(_("Target Forecourt Shift is required to run an import."))

	provider_doc = frappe.get_doc("Payment Provider", batch_doc.provider)
	mapping = _load_mapping(provider_doc)
	import_format = (provider_doc.import_format or "").lower()

	content = _read_attached_file(batch_doc)

	if "excel" in import_format:
		rows = _parse_excel(content, mapping)
	else:
		rows = _parse_csv(content, mapping)

	shift_doc = frappe.get_doc("Forecourt Shift", batch_doc.forecourt_shift)

	existing_refs: set[str] = {r.reference for r in shift_doc.collections if r.reference}
	till_map: dict[str, str] = mapping.get("till_to_cashier") or {}
	default_cashier: str = mapping.get("default_cashier") or ""
	cashier_list: list[str] = [c.cashier for c in shift_doc.cashiers if c.cashier]

	created = 0
	duplicates = 0
	rejected = 0
	log_lines: list[str] = []

	for idx, row in enumerate(rows, start=2):
		ref = row.get("reference") or ""
		amount = flt(row.get("amount") or 0, 2)

		if not ref:
			log_lines.append(f"Row {idx}: skipped — no reference")
			rejected += 1
			continue

		if not amount:
			log_lines.append(f"Row {idx}: skipped — zero amount ({ref})")
			rejected += 1
			continue

		if ref in existing_refs:
			duplicates += 1
			continue

		cashier = _resolve_cashier(
			till=row.get("till") or "",
			till_map=till_map,
			default_cashier=default_cashier,
			cashier_list=cashier_list,
		)
		if not cashier:
			log_lines.append(f"Row {idx}: rejected — cannot assign cashier (ref {ref})")
			rejected += 1
			continue

		collection_type = _collection_type_for_provider(provider_doc)
		shift_doc.append(
			"collections",
			{
				"cashier": cashier,
				"collection_type": collection_type,
				"provider": batch_doc.provider,
				"reference": ref,
				"amount": amount,
				"till_or_terminal": row.get("till") or "",
				"payer": row.get("payer") or "",
				"transaction_time": row.get("transaction_time") or None,
				"import_batch": batch_doc.name,
			},
		)
		existing_refs.add(ref)
		created += 1

	if created:
		shift_doc.flags.ignore_validate = True
		shift_doc.save()

	log_text = "\n".join(log_lines)
	frappe.db.set_value(
		"Payment Import Batch",
		batch_doc.name,
		{
			"rows_read": len(rows),
			"rows_created": created,
			"rows_duplicate": duplicates,
			"rows_rejected": rejected,
			"log": log_text,
		},
		update_modified=True,
	)

	return {
		"rows_read": len(rows),
		"rows_created": created,
		"rows_duplicate": duplicates,
		"rows_rejected": rejected,
	}


@frappe.whitelist()
def run_for_shift(shift: str, provider: str, file_url: str) -> dict:
	"""Create a Payment Import Batch and run it.

	Called from the Import Transactions button on the Forecourt Shift form.
	Returns the same summary dict as run().
	"""
	shift_doc = frappe.get_doc("Forecourt Shift", shift)
	frappe.has_permission("Forecourt Shift", "write", shift_doc, throw=True)

	batch_doc = frappe.get_doc(
		{
			"doctype": "Payment Import Batch",
			"station": shift_doc.station,
			"forecourt_shift": shift,
			"provider": provider,
			"file": file_url,
		}
	)
	batch_doc.insert()

	return run(batch_doc.name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_mapping(provider_doc: "frappe.Document") -> dict:
	raw = provider_doc.import_mapping or "{}"
	if isinstance(raw, str):
		try:
			return json.loads(raw)
		except (json.JSONDecodeError, ValueError):
			return {}
	if isinstance(raw, dict):
		return raw
	return {}


def _read_attached_file(batch_doc: "frappe.Document") -> bytes:
	file_docs = frappe.get_all(
		"File",
		filters={"file_url": batch_doc.file},
		fields=["name"],
		order_by="creation desc",
		limit=1,
	)
	if not file_docs:
		frappe.throw(_("Attached file not found for batch {0}.").format(batch_doc.name))
	file_doc = frappe.get_doc("File", file_docs[0].name)
	content = file_doc.get_content()
	if isinstance(content, str):
		content = content.encode("utf-8")
	return content


def _parse_csv(content: bytes, mapping: dict) -> list[dict]:
	text = content.decode("utf-8-sig", errors="replace")
	reader = csv.DictReader(io.StringIO(text))
	return [_map_row(row, mapping) for row in reader]


def _parse_excel(content: bytes, mapping: dict) -> list[dict]:
	import openpyxl

	wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
	ws = wb.active
	rows_iter = iter(ws.rows)
	headers = [cell.value for cell in next(rows_iter)]
	result = []
	for cells in rows_iter:
		raw = {headers[i]: cells[i].value for i in range(len(headers)) if headers[i] is not None}
		result.append(_map_row(raw, mapping))
	wb.close()
	return result


def _map_row(raw: dict[str, Any], mapping: dict) -> dict:
	"""Apply import_mapping to a raw row dict."""
	ref_col = mapping.get("reference", "")
	amount_col = mapping.get("amount", "")
	till_col = mapping.get("till", "")
	payer_col = mapping.get("payer", "")
	time_col = mapping.get("transaction_time", "")

	return {
		"reference": _cell(raw, ref_col),
		"amount": _cell(raw, amount_col),
		"till": _cell(raw, till_col),
		"payer": _cell(raw, payer_col),
		"transaction_time": _cell(raw, time_col),
	}


def _cell(row: dict, col: str) -> Any:
	if not col:
		return None
	return row.get(col)


def _resolve_cashier(
	till: str,
	till_map: dict[str, str],
	default_cashier: str,
	cashier_list: list[str],
) -> str:
	if till and till_map:
		matched = till_map.get(str(till))
		if matched:
			return matched
	if default_cashier:
		return default_cashier
	if cashier_list:
		return cashier_list[0]
	return ""


def _collection_type_for_provider(provider_doc: "frappe.Document") -> str:
	ptype = provider_doc.provider_type or ""
	if ptype == "Mobile Money":
		return "Mobile Money"
	if ptype == "Card":
		return "Card"
	if ptype == "Voucher":
		return "Voucher"
	return "Mobile Money"
