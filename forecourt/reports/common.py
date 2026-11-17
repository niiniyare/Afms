"""
FMS report helpers — shared across all Script Reports (FMS-R02).

Permissions:
  Every report must call apply_station_permission() early in _data(); it
  raises FMS-R902 if the user has no access to any station in scope.

Date filters:
  apply_date_filter(f, filters, date_field="posting_date")
    Apply from_date / to_date to filter dict f in-place.
    date_field selects which field to filter on.
  apply_shift_date_filter(f, filters)
    Same but uses shift_date (for Forecourt Shift queries).

Date field semantics (not interchangeable):
  posting_date  — SLE, CLE, NLE, WLE, Payment Entry (shift posting date)
  shift_date    — Forecourt Shift (the shift date itself)
  transaction_time — Payment Feed Entry (provider transaction datetime)
  date (single) — "as of" snapshots: cash_position, run_out_forecast, tank_stock_position

Totals profiles:
  T-ADD  total_row_add()   — sum all numeric columns
  T-WTD  total_row_wtd()   — sum additive cols, recompute weighted cols
  T-BAL  (no helper; caller builds opening/closing manually)
  T-REG  total_row_reg()   — count rows + sum numeric
  T-RANK total_row_rank()  — network-average row
  T-PIVOT (no helper; caller builds matrix manually)

Tree rows:
  make_tree_rows() — wrap flat data in group/detail rows with indent levels.

Summary cards (max 4 per report):
  summary_card()

Validation:
  validate_date_range()

Error messages (design guide 15.3):
  FMS-R801 from_date > to_date
  FMS-R802 range exceeds max_days
  FMS-R902 no station access
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from forecourt.permissions import get_permitted_stations

# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

_MAX_DETAIL_DAYS = 366
_MAX_AGGREGATE_DAYS = 1096  # 3 years


def permitted_stations(user: str | None = None) -> list[str] | None:
	"""Return station list for *user* (None = unrestricted), or [] if no access."""
	return get_permitted_stations(user or frappe.session.user)


def permitted_companies(user: str | None = None) -> list[str]:
	"""Return company names the user has User Permissions for, or all companies."""
	u = user or frappe.session.user
	all_perms = frappe.permissions.get_user_permissions(u)
	company_perms = all_perms.get("Company", [])
	if company_perms:
		return [p.get("doc") for p in company_perms if p.get("doc")]
	return frappe.get_all("Company", pluck="name")


def apply_station_permission(
	f: dict,
	filters: dict,
	user: str | None = None,
) -> str | None:
	"""
	Intersect the user's permitted stations with any station/company filter
	the user has requested.  Mutates *f* in-place.

	Returns None on success, or an FMS-R902 error message string when no
	stations remain in scope (caller should return early with that message).
	"""
	u = user or frappe.session.user
	permitted = permitted_stations(u)

	# Build candidate set from explicit station filter
	if filters.get("station"):
		candidates = [filters["station"]]
	elif filters.get("company"):
		# restrict to stations belonging to the requested company
		candidates = frappe.get_all(
			"Station",
			filters={"company": filters["company"]},
			pluck="name",
		)
	else:
		candidates = None  # no scope filter

	if permitted is None:
		# unrestricted user — apply any explicit filter as-is
		if candidates is not None:
			f["station"] = ["in", candidates]
		return None

	# restricted user — intersect
	if candidates is not None:
		allowed = [s for s in candidates if s in permitted]
	else:
		allowed = permitted

	if not allowed:
		return no_permission_message()

	f["station"] = ["in", allowed]
	return None


# ---------------------------------------------------------------------------
# Base filter builder
# ---------------------------------------------------------------------------


def base_ledger_filters(
	filters: dict,
	include_history: bool = False,
) -> dict:
	"""
	Build the base filter dict for any ledger DocType query.

	Sets is_cancelled=0 and superseded_by not set unless include_history=True.
	Does NOT add station / company / date — callers add those themselves.
	"""
	f: dict = {}
	if not include_history:
		f["is_cancelled"] = 0
		f["superseded_by"] = ["is", "not set"]
	return f


# ---------------------------------------------------------------------------
# Date filter helpers
# ---------------------------------------------------------------------------


def apply_date_filter(
	f: dict,
	filters: dict,
	date_field: str = "posting_date",
) -> None:
	"""
	Apply from_date / to_date from *filters* to filter dict *f* in-place.

	Uses *date_field* as the target field name.  Pass date_field="shift_date"
	for Forecourt Shift queries; default "posting_date" for all ledger queries.

	Both dates present  → ["between", [from_date, to_date]]
	Only from_date      → [">=", from_date]
	Only to_date        → ["<=", to_date]
	Neither             → no change to f
	"""
	fd = filters.get("from_date")
	td = filters.get("to_date")
	if fd and td:
		f[date_field] = ["between", [fd, td]]
	elif fd:
		f[date_field] = [">=", fd]
	elif td:
		f[date_field] = ["<=", td]


def apply_shift_date_filter(f: dict, filters: dict) -> None:
	"""Convenience wrapper: apply_date_filter with date_field='shift_date'."""
	apply_date_filter(f, filters, date_field="shift_date")


# ---------------------------------------------------------------------------
# Date range validation
# ---------------------------------------------------------------------------


def validate_date_range(
	from_date,
	to_date,
	max_days: int = _MAX_DETAIL_DAYS,
) -> str | None:
	"""
	Return an FMS-R8xx error message string if the range is invalid, else None.
	"""
	if not from_date or not to_date:
		return None

	from frappe.utils import date_diff, getdate

	fd = getdate(from_date)
	td = getdate(to_date)

	if fd > td:
		return _("FMS-R801: From Date {0} is after To Date {1}. Swap the dates.").format(from_date, to_date)

	span = date_diff(td, fd) + 1
	if span > max_days:
		return _("FMS-R802: Date range spans {0} days (max {1}). Narrow the range.").format(span, max_days)

	return None


# ---------------------------------------------------------------------------
# T-ADD: simple additive totals
# ---------------------------------------------------------------------------


def total_row_add(
	data: list[dict],
	columns: list[dict],
	label: str = "",
) -> dict:
	"""
	T-ADD totals row: sum every Float/Currency/Int column.

	*label* goes in the first Data/Link column; leave blank for no label.
	"""
	row: dict = {}
	first_text = True
	for col in columns:
		fn = col.get("fieldname", "")
		ft = col.get("fieldtype", "")
		if ft in ("Float", "Currency", "Int", "Percent"):
			row[fn] = flt(sum(flt(d.get(fn) or 0) for d in data), _col_precision(col))
		elif first_text:
			row[fn] = label or _("Total")
			first_text = False
		else:
			row[fn] = ""
	row["bold"] = 1
	return row


# ---------------------------------------------------------------------------
# T-WTD: weighted totals (additive cols summed; computed cols recalculated)
# ---------------------------------------------------------------------------


def total_row_wtd(
	data: list[dict],
	columns: list[dict],
	computed: list[dict] | None = None,
	label: str = "",
) -> dict:
	"""
	T-WTD totals row.

	*computed* is a list of dicts describing columns whose total value must be
	derived from summed components rather than summed directly::

	    [
	        {
	            "fieldname": "avg_price",
	            "numerator": "amount",
	            "denominator": "qty",
	            "multiplier": 1,
	            "precision": 2,
	        },
	        {
	            "fieldname": "variance_pct",
	            "numerator": "variance_l",
	            "denominator": "sales_l",
	            "multiplier": 100,
	            "precision": 2,
	        },
	    ]

	Columns named in *computed* are excluded from the simple sum pass.
	"""
	computed_fields = {c["fieldname"] for c in (computed or [])}

	row: dict = {}
	first_text = True
	for col in columns:
		fn = col.get("fieldname", "")
		ft = col.get("fieldtype", "")
		if fn in computed_fields:
			row[fn] = None  # filled below
		elif ft in ("Float", "Currency", "Int", "Percent"):
			row[fn] = flt(sum(flt(d.get(fn) or 0) for d in data), _col_precision(col))
		elif first_text:
			row[fn] = label or _("Total")
			first_text = False
		else:
			row[fn] = ""

	for spec in computed or []:
		fn = spec["fieldname"]
		num = flt(sum(flt(d.get(spec["numerator"]) or 0) for d in data))
		den = flt(sum(flt(d.get(spec["denominator"]) or 0) for d in data))
		mult = flt(spec.get("multiplier", 1))
		prec = int(spec.get("precision", 2))
		row[fn] = flt((num / den * mult) if den else 0, prec)

	row["bold"] = 1
	return row


# ---------------------------------------------------------------------------
# T-REG: register totals (count rows + sum numeric)
# ---------------------------------------------------------------------------


def total_row_reg(
	data: list[dict],
	columns: list[dict],
	count_label: str = "",
	label: str = "",
) -> dict:
	"""
	T-REG totals row: row count in the first column, sums in numeric columns.

	*count_label* is the column fieldname that should show the count; if blank,
	the count goes into the first Data/Link column.
	"""
	row = total_row_add(data, columns, label=label or _("Total"))
	if count_label:
		row[count_label] = len(data)
	row["bold"] = 1
	return row


# ---------------------------------------------------------------------------
# T-RANK: network-average row (denominator = count of non-zero rows per col)
# ---------------------------------------------------------------------------


def total_row_rank(
	data: list[dict],
	columns: list[dict],
	computed: list[dict] | None = None,
	label: str = "",
) -> dict:
	"""
	T-RANK totals row: average across data rows (network average).

	Weighted columns (in *computed*) are recalculated from their sums, same as
	total_row_wtd().  Other numeric columns are averaged over non-zero rows.
	"""
	computed_fields = {c["fieldname"] for c in (computed or [])}

	row: dict = {}
	first_text = True
	for col in columns:
		fn = col.get("fieldname", "")
		ft = col.get("fieldtype", "")
		if fn in computed_fields:
			row[fn] = None
		elif ft in ("Float", "Currency", "Int", "Percent"):
			vals = [flt(d.get(fn) or 0) for d in data if (d.get(fn) or 0) != 0]
			row[fn] = flt(sum(vals) / len(vals) if vals else 0, _col_precision(col))
		elif first_text:
			row[fn] = label or _("Network Average")
			first_text = False
		else:
			row[fn] = ""

	for spec in computed or []:
		fn = spec["fieldname"]
		num = flt(sum(flt(d.get(spec["numerator"]) or 0) for d in data))
		den = flt(sum(flt(d.get(spec["denominator"]) or 0) for d in data))
		mult = flt(spec.get("multiplier", 1))
		prec = int(spec.get("precision", 2))
		row[fn] = flt((num / den * mult) if den else 0, prec)

	row["bold"] = 1
	return row


# ---------------------------------------------------------------------------
# Tree rows
# ---------------------------------------------------------------------------


def make_tree_rows(
	data: list[dict],
	group_key: str,
	group_label_fn=None,
	group_total_fn=None,
	sort_key=None,
) -> list[dict]:
	"""
	Wrap flat *data* in group/detail rows using the ``indent`` convention.

	indent=0 — group header row (bold, no_data=1)
	indent=1 — detail row

	*group_label_fn(group_value) -> str*: label for the group row (default: group value)
	*group_total_fn(group_value, rows) -> dict*: extra fields for the group row
	                                              (e.g. totals); default: empty dict
	*sort_key*: sort group keys before building rows; None = natural order

	Returns list ready for Frappe tree reports (set ``tree: true`` in report JS).
	"""
	# Group by group_key preserving order of first occurrence
	groups: dict[str, list[dict]] = {}
	for row in data:
		gv = row.get(group_key) or ""
		groups.setdefault(gv, []).append(row)

	if sort_key is not None:
		sorted_keys = sorted(groups.keys(), key=sort_key)
	else:
		sorted_keys = list(groups.keys())

	out: list[dict] = []
	for gv in sorted_keys:
		rows = groups[gv]
		label = group_label_fn(gv) if group_label_fn else (gv or "—")
		extra = group_total_fn(gv, rows) if group_total_fn else {}
		group_row: dict = {group_key: label, "indent": 0, "bold": 1, **extra}
		out.append(group_row)
		for r in rows:
			out.append({**r, "indent": 1})

	return out


# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------


def summary_card(
	value,
	label: str,
	datatype: str = "Float",
	currency: str | None = None,
	indicator: str = "Blue",
) -> dict:
	"""
	Build one summary card dict for the 5th return value of execute().

	*indicator*: Green | Blue | Orange | Red | Grey
	"""
	card: dict = {"value": value, "label": label, "datatype": datatype, "indicator": indicator}
	if currency:
		card["currency"] = currency
	return card


# ---------------------------------------------------------------------------
# Standard message helpers
# ---------------------------------------------------------------------------


def no_data_message() -> str:
	return _("No records found for the selected filters.")


def no_permission_message(detail: str = "") -> str:
	msg = _("FMS-R902: You do not have access to any station in this scope.")
	if detail:
		msg += f" {detail}"
	return msg


# ---------------------------------------------------------------------------
# Internal utility
# ---------------------------------------------------------------------------


def _col_precision(col: dict) -> int:
	if col.get("fieldtype") == "Currency":
		return 2
	return int(col.get("precision", 3) or 3)
