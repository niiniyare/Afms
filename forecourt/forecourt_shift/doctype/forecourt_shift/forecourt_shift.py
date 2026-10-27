"""Forecourt Shift controller.

F01: DocType structure.
F02: before_insert pre-fill.
F03: validate calculations.
F04: meter modes/drift gate.
F05: pull GRN receipts and own use into tank dip rows; chart-mode dip.
F06: pull own use into meter reading rows; FMS-S113 draft own-use gate.
F07: FMS-S112 gate: every price segment must have meter readings.
F08: credit sale rates, over-limit flags, FMS-S107 gate.
F09: POS pull-in into item_sales.
F10: collection reference uniqueness, expense limits, FMS-S114 gate.
F11: resolution lines; FMS-S105 (cashier resolved) and FMS-S106 (tank variance approved) gates.
F12: remaining before_submit gates (S101-S104, S108-S111, S115); errors collected and thrown together.
F13: on_submit posts Sales Invoices and Payment Entries via posting/sales.py and posting/payments.py.
F14: on_submit also posts JE (expenses + differences) and Stock Reconciliation via posting/journals.py and posting/stock.py.
F15: on_submit writes four FMS ledgers and updates Nozzle last_* readings via posting/ledgers.py.
F16: background close via forecourt_shift/close.py; before_submit blocks accidental Submit on "Closing" shifts.
"""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime

from forecourt.calc import calibration as calc_calibration
from forecourt.calc import cashier as calc_cashier
from forecourt.calc import drift as calc_drift
from forecourt.calc import meters as calc_meters
from forecourt.calc import reconciliation as calc_reconciliation
from forecourt.errors import (
	FMS_S101,
	FMS_S102,
	FMS_S103,
	FMS_S104,
	FMS_S105,
	FMS_S106,
	FMS_S107,
	FMS_S108,
	FMS_S109,
	FMS_S110,
	FMS_S111,
	FMS_S112,
	FMS_S113,
	FMS_S114,
	FMS_S115,
	FMS_W103,
)


class ForecourtShift(Document):
	# ------------------------------------------------------------------ F04 / F06 / F07 / F08 / F10 / F11 / F12 / F13 / F16
	def before_submit(self) -> None:
		"""Collect all gate failures then throw together (FMS-S101 to S115, W103)."""
		if self.status == "Closing" and not frappe.flags.fms_background_close:
			frappe.throw(
				_("[FMS-F16] Shift {0} is being closed in background. Please wait.").format(self.name)
			)
		errors: list[str] = []
		self._gate_nozzle_readings(errors)
		self._gate_reading_continuity(errors)
		self._gate_tank_dips_required(errors)
		self._gate_nozzle_cashier(errors)
		self._gate_drift_reason(errors)
		self._gate_no_draft_own_use(errors)
		self._gate_segment_readings(errors)
		self._gate_credit_over_limit(errors)
		self._gate_credit_volume(errors)
		self._gate_expenses(errors)
		self._gate_no_overlap(errors)
		self._gate_feed_entries(errors)
		self._gate_collection_refs(errors)
		self._gate_cashier_resolved(errors)
		self._gate_tank_variance_approved(errors)
		self._gate_test_volume(errors)
		if errors:
			frappe.throw("<br>".join(errors), title=_("Shift Cannot Be Closed"))

	# ------------------------------------------------------------------ F13 / F14
	def on_submit(self) -> None:
		"""Post all shift documents: invoices, payments, journals, stock and ledgers."""
		from forecourt.posting import journals as posting_journals
		from forecourt.posting import ledgers as posting_ledgers
		from forecourt.posting import payments as posting_payments
		from forecourt.posting import sales as posting_sales
		from forecourt.posting import stock as posting_stock

		# F13: invoices first (stock consumption before tank adjustment)
		credit_invoices = posting_sales.post_credit_invoices(self)
		walkin_invoice = posting_sales.post_walkin_invoice(self)
		posting_payments.post_payment_entries(self, walkin_invoice, credit_invoices)

		# F14: JE for expenses + differences, then stock
		posting_journals.post_expense_and_difference_je(self)
		posting_stock.post_stock_reconciliations(self)
		posting_stock.post_drop_entries(self)
		posting_stock.post_float_returns(self)

		# F15: FMS ledgers and nozzle last readings
		posting_ledgers.write_shift_wetstock_ledger(self)
		posting_ledgers.write_shift_nozzle_ledger(self)
		posting_ledgers.write_shift_sales_ledger(self)
		posting_ledgers.write_shift_cashier_ledger(self)
		posting_ledgers.update_nozzle_last_readings(self)

	# ------------------------------------------------------------------ F12 new gates

	def _gate_nozzle_readings(self, errors: list[str]) -> None:
		"""FMS-S101: every active nozzle has a closing reading >= opening, or rollover ticked."""
		problems = []
		for row in self.meter_readings:
			if not row.nozzle:
				continue
			if row.rec_elec_cash:
				if not row.closing_elec_cash:
					problems.append(_("nozzle {0} e-cash (missing closing)").format(row.nozzle))
				elif flt(row.closing_elec_cash) < flt(row.opening_elec_cash) and not row.rollover_elec_cash:
					problems.append(_("nozzle {0} e-cash").format(row.nozzle))
			if row.rec_elec_meter:
				if not row.closing_elec_meter:
					problems.append(_("nozzle {0} e-vol (missing closing)").format(row.nozzle))
				elif (
					flt(row.closing_elec_meter) < flt(row.opening_elec_meter) and not row.rollover_elec_meter
				):
					problems.append(_("nozzle {0} e-vol").format(row.nozzle))
			if row.rec_man_meter:
				if not row.closing_man_meter:
					problems.append(_("nozzle {0} m-vol (missing closing)").format(row.nozzle))
				elif flt(row.closing_man_meter) < flt(row.opening_man_meter) and not row.rollover_man_meter:
					problems.append(_("nozzle {0} m-vol").format(row.nozzle))
		if problems:
			errors.append(
				_("{0}: Closing reading below opening on {1}. Correct the reading or tick Rollover.").format(
					FMS_S101, ", ".join(problems)
				)
			)

	def _gate_reading_continuity(self, errors: list[str]) -> None:
		"""FMS-S102: opening readings must match previous shift's closing readings."""
		if not self.previous_shift:
			return
		prev_readings = frappe.get_all(
			"Shift Meter Reading",
			filters={"parent": self.previous_shift},
			fields=["nozzle", "closing_elec_cash", "closing_elec_meter", "closing_man_meter", "segment_no"],
			order_by="segment_no desc",
		)
		prev_closing: dict[str, object] = {}
		for r in prev_readings:
			if r.nozzle not in prev_closing:
				prev_closing[r.nozzle] = r
		problems = []
		for row in self.meter_readings:
			if int(row.segment_no or 1) != 1 or not row.nozzle:
				continue
			prev = prev_closing.get(row.nozzle)
			if not prev:
				continue
			if row.rec_elec_cash and flt(row.opening_elec_cash, 3) != flt(prev.closing_elec_cash, 3):
				problems.append(_("nozzle {0} e-cash").format(row.nozzle))
			if row.rec_elec_meter and flt(row.opening_elec_meter, 3) != flt(prev.closing_elec_meter, 3):
				problems.append(_("nozzle {0} e-vol").format(row.nozzle))
			if row.rec_man_meter and flt(row.opening_man_meter, 3) != flt(prev.closing_man_meter, 3):
				problems.append(_("nozzle {0} m-vol").format(row.nozzle))
		if problems:
			errors.append(
				_(
					"{0}: Opening reading does not match previous closing on {1}. Re-fetch openings or check the previous shift."
				).format(FMS_S102, ", ".join(problems))
			)

	def _gate_tank_dips_required(self, errors: list[str]) -> None:
		"""FMS-S103: every tank requiring a dip has one."""
		if not self.shift_template:
			return
		dips_required = bool(
			frappe.db.get_value("Forecourt Shift Template", self.shift_template, "dips_required")
		)
		if not dips_required:
			return
		missing = [row.tank for row in self.tank_dips if not flt(row.dip_l) and not flt(row.dip_mm)]
		if missing:
			errors.append(
				_("{0}: Tanks have no closing dip: {1}. Enter the closing dip.").format(
					FMS_S103, ", ".join(missing)
				)
			)

	def _gate_nozzle_cashier(self, errors: list[str]) -> None:
		"""FMS-S104: every nozzle reading row must have a cashier assigned."""
		missing = [row.nozzle for row in self.meter_readings if not row.cashier]
		if missing:
			errors.append(
				_("{0}: Nozzle reading rows have no cashier: {1}. Assign each to a cashier.").format(
					FMS_S104, ", ".join(missing)
				)
			)

	def _gate_credit_volume(self, errors: list[str]) -> None:
		"""FMS-S108: credit litres per product must not exceed metered litres."""
		credit_by_item: dict[str, float] = defaultdict(float)
		for row in self.credit_sales:
			if row.item:
				credit_by_item[row.item] += flt(row.qty)
		metered_by_item: dict[str, float] = defaultdict(float)
		for row in self.meter_readings:
			if row.item:
				metered_by_item[row.item] += flt(row.net_volume_l)
		problems = []
		for item, credit_qty in credit_by_item.items():
			metered = metered_by_item.get(item, 0.0)
			if flt(credit_qty, 3) > flt(metered, 3):
				problems.append(
					_("{0} (credit {1} L, metered {2} L)").format(item, flt(credit_qty, 3), flt(metered, 3))
				)
		if problems:
			errors.append(
				_("{0}: Credit litres exceed metered litres for {1}. Check slips and meter readings.").format(
					FMS_S108, "; ".join(problems)
				)
			)

	def _gate_expenses(self, errors: list[str]) -> None:
		"""FMS-S109: expense collections need a type and must be within the per-expense limit."""
		settings = frappe.get_cached_doc("Forecourt Settings")
		per_expense_limit = flt(getattr(settings, "per_expense_limit", 0) or 0)
		problems = []
		for row in self.collections:
			if row.collection_type != "Expense":
				continue
			if not row.expense_type:
				problems.append(_("Row {0}: missing expense type.").format(row.idx))
			elif per_expense_limit and flt(row.amount) > per_expense_limit:
				problems.append(
					_("Row {0}: amount {1} exceeds limit {2}.").format(
						row.idx, flt(row.amount, 2), per_expense_limit
					)
				)
		if problems:
			errors.append(_("{0}: ").format(FMS_S109) + " ".join(problems))

	def _gate_no_overlap(self, errors: list[str]) -> None:
		"""FMS-S110: shift window must not overlap another submitted shift at this station."""
		if not self.station or not self.shift_start or not self.shift_end:
			return
		if self.company and frappe.db.exists("DocType", "Forecourt Company Settings"):
			allow_overlap = frappe.db.get_value(
				"Forecourt Company Settings", self.company, "allow_overlapping_shifts"
			)
			if allow_overlap:
				return
		overlapping = frappe.get_all(
			"Forecourt Shift",
			filters={
				"station": self.station,
				"docstatus": 1,
				"name": ["!=", self.name or ""],
				"shift_start": ["<", self.shift_end],
				"shift_end": [">", self.shift_start],
			},
			fields=["name"],
			limit=1,
		)
		if overlapping:
			errors.append(
				_("{0}: Shift window overlaps shift {1} at this station. Fix the date or template.").format(
					FMS_S110, overlapping[0].name
				)
			)

	def _gate_feed_entries(self, errors: list[str]) -> None:
		"""FMS-S111: all payment feed entries in the window must be assigned to a cashier."""
		if not frappe.db.exists("DocType", "Payment Feed Entry"):
			return
		if not (self.station and self.shift_start and self.shift_end):
			return
		unassigned_count = frappe.db.count(
			"Payment Feed Entry",
			{
				"station": self.station,
				"posting_datetime": ["between", [self.shift_start, self.shift_end]],
				"cashier": ["is", "not set"],
				"docstatus": 1,
			},
		)
		if unassigned_count:
			errors.append(
				_("{0}: {1} payment feed entries in the shift window are not assigned to a cashier.").format(
					FMS_S111, unassigned_count
				)
			)

	def _gate_test_volume(self, errors: list[str]) -> None:
		"""FMS-S115: test volume per nozzle must not exceed the nozzle's per-shift limit (D29)."""
		problems = []
		for row in self.meter_readings:
			if not row.nozzle or not flt(row.test_volume_l):
				continue
			max_test = flt(frappe.db.get_value("Nozzle", row.nozzle, "max_test_volume_l") or 0)
			if max_test and flt(row.test_volume_l, 3) > max_test:
				problems.append(
					_("nozzle {0} ({1} L > limit {2} L)").format(
						row.nozzle, flt(row.test_volume_l, 3), max_test
					)
				)
		if problems:
			errors.append(
				_("{0}: Test volume exceeds nozzle limit on {1}. Correct the test volume.").format(
					FMS_S115, "; ".join(problems)
				)
			)

	# ------------------------------------------------------------------ F04 / F06 / F07 / F10 / F11 existing gates (refactored to collect)

	def _gate_drift_reason(self, errors: list[str]) -> None:
		settings = frappe.get_cached_doc("Forecourt Settings")
		if not getattr(settings, "drift_requires_reason", True):
			return
		missing = [row.nozzle for row in self.meter_readings if row.drift_breach and not row.drift_reason]
		if missing:
			errors.append(
				_("{0}: Drift beyond tolerance on {1} — record the reason before closing.").format(
					FMS_W103, ", ".join(missing)
				)
			)

	def _gate_no_draft_own_use(self, errors: list[str]) -> None:
		"""FMS-S113: no draft Fuel Own Use entry may exist inside the shift window."""
		if not (self.station and self.shift_start and self.shift_end):
			return
		start_dt = get_datetime(self.shift_start)
		end_dt = get_datetime(self.shift_end)
		start_date = start_dt.date() if hasattr(start_dt, "date") else start_dt
		end_date = end_dt.date() if hasattr(end_dt, "date") else end_dt
		drafts = frappe.get_all(
			"Stock Entry",
			filters={
				"station": self.station,
				"stock_entry_type": "Fuel Own Use",
				"docstatus": 0,
				"posting_date": ["between", [str(start_date), str(end_date)]],
			},
			fields=["name", "posting_date", "posting_time"],
		)
		blocking = [
			e.name
			for e in drafts
			if start_dt <= get_datetime(f"{e.posting_date} {e.posting_time or '00:00:00'}") < end_dt
		]
		if blocking:
			errors.append(
				_("{0}: Draft Fuel Own Use entries in the shift window: {1}. Submit or delete them.").format(
					FMS_S113, ", ".join(blocking)
				)
			)

	def _gate_segment_readings(self, errors: list[str]) -> None:
		"""FMS-S112: every price segment must have closing meter readings."""
		missing = []
		for price_row in self.prices:
			item = price_row.item
			seg = int(price_row.segment_no or 1)
			has_reading = any(
				r.item == item
				and int(r.segment_no or 1) == seg
				and (r.closing_elec_cash or r.closing_elec_meter or r.closing_man_meter)
				for r in self.meter_readings
			)
			if not has_reading:
				missing.append(f"{item} seg {seg}")
		if missing:
			errors.append(
				_("{0}: Missing meter readings for {1}. Enter readings for all segments.").format(
					FMS_S112, ", ".join(missing)
				)
			)

	def _gate_credit_over_limit(self, errors: list[str]) -> None:
		"""FMS-S107: over-limit credit sales must be approved."""
		blocking = [
			f"{r.customer} slip {r.slip_no}"
			for r in self.credit_sales
			if r.over_limit and not r.over_limit_approved_by
		]
		if blocking:
			errors.append(
				_("{0}: Over-limit credit sales require approval: {1}.").format(FMS_S107, ", ".join(blocking))
			)

	def _gate_collection_refs(self, errors: list[str]) -> None:
		"""FMS-S114: mobile money and card collections require unique references per provider."""
		seen: dict[str, str] = {}
		problems = []
		for row in self.collections:
			if row.collection_type not in ("Mobile Money", "Card"):
				continue
			if not row.reference:
				problems.append(
					_("Row {0}: {1} collection missing reference.").format(row.idx, row.collection_type)
				)
				continue
			key = f"{row.provider or ''}:{row.reference}"
			if key in seen:
				problems.append(
					_("Row {0}: reference {1} already used in row {2}.").format(
						row.idx, row.reference, seen[key]
					)
				)
			else:
				seen[key] = str(row.idx)
		if problems:
			errors.append(_("{0}: ").format(FMS_S114) + " ".join(problems))

	def _gate_cashier_resolved(self, errors: list[str]) -> None:
		"""FMS-S105: every cashier with a non-zero difference must have a resolution line."""
		unresolved = [
			row.cashier for row in self.cashiers if flt(row.difference, 2) != 0 and not row.resolved
		]
		if unresolved:
			errors.append(
				_(
					"{0}: Unresolved cashier differences for {1}. Add a resolution line before closing."
				).format(FMS_S105, ", ".join(unresolved))
			)

	def _gate_tank_variance_approved(self, errors: list[str]) -> None:
		"""FMS-S106: tank variances outside tolerance need a reason; above approval threshold, approval."""
		problems = []
		for row in self.tank_dips:
			if row.within_tolerance:
				continue
			if not row.reason:
				problems.append(_("Tank {0}: variance outside tolerance has no reason.").format(row.tank))
			elif row.needs_approval and not row.approved_by:
				problems.append(
					_("Tank {0}: variance above approval threshold is not approved.").format(row.tank)
				)
		if problems:
			errors.append(_("{0}: ").format(FMS_S106) + " ".join(problems))

	# ------------------------------------------------------------------ F08 helpers

	def _compute_credit_sale_rates(self) -> None:
		"""Set rate and amount on credit sale rows from the shift's price segments."""
		for row in self.credit_sales:
			if not (row.item and row.sold_at):
				continue
			rate = self._get_segment_price(row.item, get_datetime(row.sold_at))
			if rate:
				row.rate = flt(rate)
				row.amount = flt(flt(row.qty) * row.rate, 2)

	def _get_segment_price(self, item: str, at_dt) -> float | None:
		for price_row in self.prices:
			if price_row.item != item:
				continue
			eff_from = get_datetime(price_row.effective_from) if price_row.effective_from else None
			eff_to = get_datetime(price_row.effective_to) if price_row.effective_to else None
			if eff_from and at_dt < eff_from:
				continue
			if eff_to and at_dt >= eff_to:
				continue
			return flt(price_row.price)
		return None

	def _flag_credit_over_limit(self) -> None:
		"""Flag credit sale rows where vehicle monthly litre limit would be exceeded."""
		if not self.shift_date:
			return
		# Sum litres per vehicle per item for this shift
		shift_vol: dict[tuple, float] = defaultdict(float)
		for row in self.credit_sales:
			if row.vehicle and row.item:
				shift_vol[(row.vehicle, row.item)] += flt(row.qty)

		for row in self.credit_sales:
			if not row.vehicle:
				row.over_limit = 0
				continue
			vehicle = frappe.get_cached_doc("Customer Vehicle", row.vehicle)
			monthly_limit = flt(getattr(vehicle, "monthly_limit_l", 0))
			if not monthly_limit:
				row.over_limit = 0
				continue
			# Sum all credit sales for this vehicle and item this calendar month
			from frappe.utils import get_first_day, get_last_day

			month_start = get_first_day(self.shift_date)
			month_end = get_last_day(self.shift_date)
			prev_qty = flt(
				frappe.db.sql(
					"""
					SELECT SUM(cs.qty)
					FROM `tabShift Credit Sale` cs
					JOIN `tabForecourt Shift` sh ON sh.name = cs.parent
					WHERE cs.vehicle = %s AND cs.item = %s
					  AND sh.shift_date BETWEEN %s AND %s
					  AND sh.docstatus = 1 AND sh.name != %s
					""",
					(row.vehicle, row.item, month_start, month_end, self.name or ""),
				)[0][0]
				or 0
			)
			total = prev_qty + shift_vol.get((row.vehicle, row.item), 0.0)
			row.over_limit = int(total > monthly_limit)

	# ------------------------------------------------------------------ F09 helpers

	def _pull_pos_items(self) -> None:
		"""Pull submitted POS Invoices/POS Sales Invoices in the window as read-only item_sales rows."""
		if not (self.station and self.shift_start and self.shift_end):
			return
		# Build cashier → employee map (Employee.user_id → Employee.name)
		cashier_employees = {row.cashier for row in self.cashiers if row.cashier}
		if not cashier_employees:
			return
		user_to_employee: dict[str, str] = {}
		for emp in frappe.get_all(
			"Employee",
			filters={"name": ["in", list(cashier_employees)]},
			fields=["name", "user_id"],
		):
			if emp.user_id:
				user_to_employee[emp.user_id] = emp.name

		start_dt = get_datetime(self.shift_start)
		end_dt = get_datetime(self.shift_end)
		start_date = start_dt.date() if hasattr(start_dt, "date") else start_dt
		end_date = end_dt.date() if hasattr(end_dt, "date") else end_dt

		# Remove previously pulled POS rows so we can re-pull cleanly
		self.item_sales = [r for r in self.item_sales if not r.pos_invoice]

		for doctype in ("POS Invoice", "Sales Invoice"):
			filters = {
				"docstatus": 1,
				"posting_date": ["between", [str(start_date), str(end_date)]],
			}
			if doctype == "Sales Invoice":
				filters["is_pos"] = 1
			invoices = frappe.get_all(
				doctype,
				filters=filters,
				fields=["name", "owner", "posting_date", "posting_time"],
			)
			for inv in invoices:
				posting_dt = get_datetime(f"{inv.posting_date} {inv.posting_time or '00:00:00'}")
				if not (start_dt <= posting_dt < end_dt):
					continue
				cashier = user_to_employee.get(inv.owner)
				if not cashier:
					continue
				# Pull non-fuel items
				items = frappe.get_all(
					f"{doctype} Item",
					filters={"parent": inv.name, "fms_is_fuel": 0}
					if doctype == "POS Invoice"
					else {"parent": inv.name},
					fields=["item_code", "qty", "rate", "amount"],
				)
				for item_row in items:
					self.append(
						"item_sales",
						{
							"cashier": cashier,
							"item": item_row.item_code,
							"qty": flt(item_row.qty),
							"rate": flt(item_row.rate),
							"amount": flt(item_row.amount),
							"pos_doctype": doctype,
							"pos_invoice": inv.name,
						},
					)

	# ------------------------------------------------------------------ F03 / F05 / F06 / F08 / F09 / F10 / F11
	def validate(self) -> None:
		self._compute_item_sale_amounts()
		self._pull_own_use_for_nozzles()  # F06
		self._compute_meter_rows()
		self._compute_credit_sale_rates()  # F08
		self._flag_credit_over_limit()  # F08
		self._pull_pos_items()  # F09
		self._compute_dip_volumes()  # F05
		self._pull_grn_receipts()  # F05
		self._pull_own_use_for_tanks()  # F05
		self._compute_tank_dip_rows()
		self._compute_cashier_rows()
		self._compute_resolution_approval()  # F11
		self._update_cashier_resolved()  # F11
		self._compute_parent_totals()

	# ------------------------------------------------------------------ F11 helpers

	def _compute_resolution_approval(self) -> None:
		"""Set needs_approval on resolution rows based on write-off and variance thresholds."""
		settings = frappe.get_cached_doc("Forecourt Settings")
		small_pct = flt(getattr(settings, "small_difference_pct", 0.1) or 0.1) / 100.0
		small_amt = flt(getattr(settings, "small_difference_amount", 0.0) or 0.0)
		tol_pct = flt(getattr(settings, "tank_tolerance_pct", 0.5) or 0.5) / 100.0
		approval_mult = flt(getattr(settings, "approval_multiplier", 2.0) or 2.0)

		cashier_expected: dict[str, float] = {c.cashier: flt(c.expected) for c in self.cashiers}
		tank_sales: dict[str, float] = {t.tank: flt(t.sales_l) for t in self.tank_dips}

		for row in self.resolutions:
			row.needs_approval = 0
			if row.action == "Write off" and flt(row.amount):
				expected = cashier_expected.get(row.cashier or "", 0.0)
				limit = max(small_pct * expected, small_amt) if expected else small_amt
				if flt(row.amount) > limit:
					row.needs_approval = 1
			elif row.action == "Accept variance" and row.tank:
				sales_l = tank_sales.get(row.tank, 0.0)
				approval_threshold = tol_pct * approval_mult * sales_l
				if sales_l and abs(flt(row.volume_l)) > approval_threshold:
					row.needs_approval = 1

	def _update_cashier_resolved(self) -> None:
		"""Set resolved=1 on cashier rows whose difference is fully covered by resolution lines."""
		resolved_amount: dict[str, float] = defaultdict(float)
		for row in self.resolutions:
			if row.resolution_for == "Cashier" and row.cashier and flt(row.amount):
				resolved_amount[row.cashier] += flt(row.amount)

		for row in self.cashiers:
			diff = flt(row.difference, 2)
			if diff == 0.0:
				row.resolved = 1
			elif flt(resolved_amount.get(row.cashier, 0.0), 2) >= abs(diff):
				row.resolved = 1
			else:
				row.resolved = 0

	# ------------------------------------------------------------------ F02
	def before_insert(self) -> None:
		"""Pre-fill the shift from the template and previous shift."""
		self._find_previous_shift()
		self._snapshot_station_settings()
		self._compute_shift_window()
		self._create_price_rows()
		self._create_reading_rows()
		self._create_tank_rows()
		self._set_title()

	# ------------------------------------------------------------------ F03 helpers

	def _compute_item_sale_amounts(self) -> None:
		for row in self.item_sales:
			row.amount = flt(flt(row.qty) * flt(row.rate), 2)

	def _compute_meter_rows(self) -> None:
		for row in self.meter_readings:
			price = flt(row.price)
			if price <= 0:
				continue

			ecash = (
				calc_meters.MeterReading(
					opening=flt(row.opening_elec_cash),
					closing=flt(row.closing_elec_cash),
					rollover=bool(row.rollover_elec_cash),
					rollover_max=flt(frappe.db.get_value("Nozzle", row.nozzle, "ecash_rollover_max") or 0),
				)
				if row.rec_elec_cash and row.closing_elec_cash
				else None
			)
			evol = (
				calc_meters.MeterReading(
					opening=flt(row.opening_elec_meter),
					closing=flt(row.closing_elec_meter),
					rollover=bool(row.rollover_elec_meter),
					rollover_max=flt(frappe.db.get_value("Nozzle", row.nozzle, "evol_rollover_max") or 0),
				)
				if row.rec_elec_meter and row.closing_elec_meter
				else None
			)
			mvol = (
				calc_meters.MeterReading(
					opening=flt(row.opening_man_meter),
					closing=flt(row.closing_man_meter),
					rollover=bool(row.rollover_man_meter),
					rollover_max=flt(frappe.db.get_value("Nozzle", row.nozzle, "mvol_rollover_max") or 0),
				)
				if row.rec_man_meter and row.closing_man_meter
				else None
			)

			if not (ecash or evol or mvol):
				continue

			try:
				result = calc_meters.segment_sales(
					ecash=ecash,
					evol=evol,
					mvol=mvol,
					price=price,
					sales_basis=row.row_sales_basis or "Elec Cash",
				)
			except ValueError:
				continue

			row.basis_meter = result.basis
			row.basis_volume_l = flt(result.basis_litres, 3)
			test_l = flt(row.test_volume_l)
			own_use_l = flt(row.own_use_l)
			row.net_volume_l = flt(result.basis_litres - test_l - own_use_l, 3)
			row.amount = flt(row.net_volume_l * price, 2)

			# drift
			ecash_l = result.ecash_litres
			evol_l = result.evol_litres
			mvol_l = result.mvol_litres
			row.drift_ecash_evol_l = flt(calc_drift.ecash_vs_evol(ecash_l, evol_l), 3)
			row.drift_ecash_mvol_l = flt(calc_drift.ecash_vs_mvol(ecash_l, mvol_l), 3)
			row.drift_evol_mvol_l = flt(calc_drift.evol_vs_mvol(evol_l, mvol_l), 3)

			max_drift = max(
				abs(row.drift_ecash_evol_l),
				abs(row.drift_ecash_mvol_l),
				abs(row.drift_evol_mvol_l),
			)
			settings = frappe.get_cached_doc("Forecourt Settings")
			tol_pct = flt(getattr(settings, "drift_tolerance_pct", 0.5) or 0.5)
			tol_l = flt(getattr(settings, "drift_tolerance_l", 2.0) or 2.0)
			row.drift_breach = int(
				not calc_drift.within_tolerance(max_drift, result.basis_litres, tol_pct, tol_l)
			)

	# ------------------------------------------------------------------ F06 helpers

	def _pull_own_use_for_nozzles(self) -> None:
		"""Pull submitted Fuel Own Use entries in shift window into meter_reading.own_use_l."""
		if not (self.station and self.shift_start and self.shift_end):
			return
		nozzles = {row.nozzle for row in self.meter_readings if row.nozzle}
		if not nozzles:
			return
		start_dt = get_datetime(self.shift_start)
		end_dt = get_datetime(self.shift_end)
		start_date = start_dt.date() if hasattr(start_dt, "date") else start_dt
		end_date = end_dt.date() if hasattr(end_dt, "date") else end_dt

		entries = frappe.get_all(
			"Stock Entry",
			filters={
				"station": self.station,
				"stock_entry_type": "Fuel Own Use",
				"docstatus": 1,
				"posting_date": ["between", [str(start_date), str(end_date)]],
			},
			fields=["name", "posting_date", "posting_time", "fms_nozzle"],
		)
		own_use: dict[str, float] = defaultdict(float)
		for entry in entries:
			if not entry.fms_nozzle or entry.fms_nozzle not in nozzles:
				continue
			posting_dt = get_datetime(f"{entry.posting_date} {entry.posting_time or '00:00:00'}")
			if not (start_dt <= posting_dt < end_dt):
				continue
			qty = flt(
				frappe.db.get_value(
					"Stock Entry Detail",
					{"parent": entry.name},
					"qty",
					order_by="idx asc",
				)
				or 0
			)
			own_use[entry.fms_nozzle] += qty

		for row in self.meter_readings:
			if row.nozzle in own_use:
				row.own_use_l = flt(own_use[row.nozzle], 3)

	# ------------------------------------------------------------------ F05 helpers

	def _compute_dip_volumes(self) -> None:
		"""Convert dip_mm to dip_l via calibration chart when dip_entry_mode is Chart."""
		for row in self.tank_dips:
			if row.dip_entry_mode != "Chart":
				continue
			chart = frappe.db.get_value(
				"Tank Calibration Chart",
				{"tank": row.tank, "valid_from": ["<=", self.shift_date or frappe.utils.today()]},
				fieldname=["name", "max_depth_mm", "max_volume_l"],
				order_by="valid_from desc",
				as_dict=True,
			)
			if not chart:
				continue
			rows_raw = frappe.get_all(
				"Tank Calibration Row",
				filters={"parent": chart.name, "parentfield": "rows"},
				fields=["depth_mm", "volume_l"],
				order_by="depth_mm asc",
			)
			water_rows_raw = frappe.get_all(
				"Tank Calibration Row",
				filters={"parent": chart.name, "parentfield": "water_rows"},
				fields=["depth_mm", "volume_l"],
				order_by="depth_mm asc",
			)
			chart_rows = [(flt(r.depth_mm), flt(r.volume_l)) for r in rows_raw]
			water_chart = [(flt(r.depth_mm), flt(r.volume_l)) for r in water_rows_raw]
			if chart_rows and row.dip_mm:
				try:
					row.dip_l = flt(calc_calibration.interpolate(flt(row.dip_mm), chart_rows), 3)
				except ValueError:
					pass
			if water_chart and row.water_mm:
				try:
					row.water_l = flt(calc_calibration.interpolate(flt(row.water_mm), water_chart), 3)
				except ValueError:
					pass

	def _pull_grn_receipts(self) -> None:
		"""Pull received_l from submitted GRNs in the shift window per tank."""
		if not (self.station and self.shift_start and self.shift_end):
			return
		tanks = {row.tank for row in self.tank_dips}
		if not tanks:
			return
		from datetime import date

		start_dt = get_datetime(self.shift_start)
		end_dt = get_datetime(self.shift_end)
		start_date = start_dt.date() if not isinstance(start_dt, date) else start_dt
		end_date = end_dt.date() if not isinstance(end_dt, date) else end_dt
		if hasattr(start_dt, "date"):
			start_date = start_dt.date()
		if hasattr(end_dt, "date"):
			end_date = end_dt.date()

		grns = frappe.get_all(
			"Purchase Receipt",
			filters={
				"station": self.station,
				"docstatus": 1,
				"posting_date": ["between", [str(start_date), str(end_date)]],
			},
			fields=["name", "posting_date", "posting_time"],
		)
		receipts: dict[str, float] = defaultdict(float)
		for grn in grns:
			posting_dt = get_datetime(f"{grn.posting_date} {grn.posting_time or '00:00:00'}")
			if start_dt <= posting_dt < end_dt:
				dip_rows = frappe.get_all(
					"GRN Delivery Dip",
					filters={"parent": grn.name, "tank": ["in", list(tanks)]},
					fields=["tank", "received_l"],
				)
				for dr in dip_rows:
					receipts[dr.tank] += flt(dr.received_l)
		for row in self.tank_dips:
			row.receipts_l = flt(receipts.get(row.tank, 0.0), 3)

	def _pull_own_use_for_tanks(self) -> None:
		"""Pull Fuel Own Use stock entries into tank_dip.own_use_l."""
		if not (self.station and self.shift_start and self.shift_end):
			return
		# Map warehouse → tank for this shift's tanks
		tank_to_warehouse: dict[str, str] = {}
		wh_to_tank: dict[str, str] = {}
		for row in self.tank_dips:
			wh = frappe.db.get_value("Fuel Tank", row.tank, "warehouse")
			if wh:
				tank_to_warehouse[row.tank] = wh
				wh_to_tank[wh] = row.tank
		if not wh_to_tank:
			return
		from datetime import date

		start_dt = get_datetime(self.shift_start)
		end_dt = get_datetime(self.shift_end)
		start_date = start_dt.date() if hasattr(start_dt, "date") else start_dt
		end_date = end_dt.date() if hasattr(end_dt, "date") else end_dt

		entries = frappe.get_all(
			"Stock Entry",
			filters={
				"station": self.station,
				"stock_entry_type": "Fuel Own Use",
				"docstatus": 1,
				"posting_date": ["between", [str(start_date), str(end_date)]],
			},
			fields=["name", "posting_date", "posting_time"],
		)
		own_use: dict[str, float] = defaultdict(float)
		for entry in entries:
			posting_dt = get_datetime(f"{entry.posting_date} {entry.posting_time or '00:00:00'}")
			if start_dt <= posting_dt < end_dt:
				items = frappe.get_all(
					"Stock Entry Detail",
					filters={"parent": entry.name, "s_warehouse": ["in", list(wh_to_tank.keys())]},
					fields=["s_warehouse", "qty"],
				)
				for item in items:
					tank = wh_to_tank.get(item.s_warehouse)
					if tank:
						own_use[tank] += flt(item.qty)
		for row in self.tank_dips:
			if row.tank in own_use:
				row.own_use_l = flt(own_use[row.tank], 3)

	def _compute_tank_dip_rows(self) -> None:
		# sum net_volume_l per tank from meter readings
		tank_sales: dict[str, float] = defaultdict(float)
		for row in self.meter_readings:
			if row.tank:
				tank_sales[row.tank] += flt(row.net_volume_l)

		for row in self.tank_dips:
			row.sales_l = flt(tank_sales.get(row.tank, 0.0), 3)

			rec = calc_reconciliation.TankReconciliation(
				opening_volume=flt(row.opening_l),
				receipts=flt(row.receipts_l),
				net_sales=flt(row.sales_l),
				own_use=flt(row.own_use_l),
				transfers=flt(row.transfers_l),
				closing_dip=flt(row.dip_l) if row.dip_l else None,
			)
			calc_reconciliation.reconcile(rec)
			row.expected_l = flt(rec.expected_closing, 3)
			if rec.variance is not None:
				row.variance_l = flt(rec.variance, 3)
				row.variance_pct = flt(rec.variance_pct or 0.0, 4)
				in_tol = calc_reconciliation.within_tolerance(rec.variance, flt(row.sales_l))
				row.within_tolerance = int(in_tol)
				row.needs_approval = int(not in_tol)

	def _compute_cashier_rows(self) -> None:
		# fuel_amount per cashier from meter readings
		fuel_amount: dict[str, float] = defaultdict(float)
		for row in self.meter_readings:
			if row.cashier:
				fuel_amount[row.cashier] += flt(row.amount)

		# item_amount per cashier from item_sales
		item_amount: dict[str, float] = defaultdict(float)
		for row in self.item_sales:
			if row.cashier:
				item_amount[row.cashier] += flt(row.amount)

		# credit per cashier from credit_sales
		credit: dict[str, float] = defaultdict(float)
		for row in self.credit_sales:
			if row.cashier:
				credit[row.cashier] += flt(row.amount)

		# cash per cashier from cash_counts
		cash_counted: dict[str, float] = defaultdict(float)
		for row in self.cash_counts:
			if row.cashier:
				cash_counted[row.cashier] += flt(row.base_amount or row.amount)

		# collections per cashier by type
		mobile: dict[str, float] = defaultdict(float)
		card: dict[str, float] = defaultdict(float)
		voucher: dict[str, float] = defaultdict(float)
		expenses: dict[str, float] = defaultdict(float)
		drops: dict[str, float] = defaultdict(float)
		debt_receipts: dict[str, float] = defaultdict(float)
		for row in self.collections:
			if not row.cashier:
				continue
			t = row.collection_type
			if t == "Mobile Money":
				mobile[row.cashier] += flt(row.amount)
			elif t == "Card":
				card[row.cashier] += flt(row.amount)
			elif t == "Voucher":
				voucher[row.cashier] += flt(row.amount)
			elif t == "Expense":
				expenses[row.cashier] += flt(row.amount)
			elif t == "Drop":
				drops[row.cashier] += flt(row.amount)
			elif t == "Debt Receipt":
				debt_receipts[row.cashier] += flt(row.amount)

		for row in self.cashiers:
			c = row.cashier
			row.fuel_amount = flt(fuel_amount.get(c, 0.0), 2)
			row.item_amount = flt(item_amount.get(c, 0.0), 2)
			row.debt_receipts = flt(debt_receipts.get(c, 0.0), 2)
			row.cash_counted = flt(cash_counted.get(c, 0.0), 2)
			row.mobile = flt(mobile.get(c, 0.0), 2)
			row.card = flt(card.get(c, 0.0), 2)
			row.credit = flt(credit.get(c, 0.0), 2)
			row.voucher = flt(voucher.get(c, 0.0), 2)
			row.expenses = flt(expenses.get(c, 0.0), 2)
			row.drops = flt(drops.get(c, 0.0), 2)

			cb = calc_cashier.CashierBalance(
				fuel_amount=row.fuel_amount,
				item_amount=row.item_amount,
				debt_receipts=row.debt_receipts,
				cash=row.cash_counted,
				mobile=row.mobile,
				card=row.card,
				credit=row.credit,
				voucher=row.voucher,
				expenses=row.expenses,
				drops=row.drops,
				opening_float=flt(row.float_amount),
			)
			calc_cashier.balance(cb)
			row.expected = flt(cb.expected, 2)
			row.accounted = flt(cb.accounted, 2)
			row.difference = flt(cb.difference, 2)

	def _compute_parent_totals(self) -> None:
		self.total_fuel_volume = flt(sum(flt(r.net_volume_l) for r in self.meter_readings), 3)
		self.total_fuel_amount = flt(sum(flt(r.amount) for r in self.meter_readings), 2)
		self.total_item_amount = flt(sum(flt(r.amount) for r in self.item_sales), 2)
		self.total_credit = flt(sum(flt(r.amount) for r in self.credit_sales), 2)

		col_mobile = col_card = col_voucher = col_exp = col_drop = 0.0
		for row in self.collections:
			t = row.collection_type
			if t == "Mobile Money":
				col_mobile += flt(row.amount)
			elif t == "Card":
				col_card += flt(row.amount)
			elif t == "Voucher":
				col_voucher += flt(row.amount)
			elif t == "Expense":
				col_exp += flt(row.amount)
			elif t == "Drop":
				col_drop += flt(row.amount)

		self.total_mobile = flt(col_mobile, 2)
		self.total_card = flt(col_card, 2)
		self.total_cash = flt(sum(flt(r.cash_counted) for r in self.cashiers), 2)
		self.total_expenses = flt(col_exp, 2)
		self.total_difference = flt(sum(flt(r.difference) for r in self.cashiers), 2)
		self.total_tank_variance_l = flt(
			sum(flt(r.variance_l) for r in self.tank_dips if r.variance_l is not None), 3
		)

	# ------------------------------------------------------------------ F02 helpers

	def _find_previous_shift(self) -> None:
		prev = frappe.get_all(
			"Forecourt Shift",
			filters={"station": self.station, "docstatus": 1},
			fields=["name"],
			order_by="shift_start desc",
			limit=1,
		)
		self.previous_shift = prev[0].name if prev else None

	def _snapshot_station_settings(self) -> None:
		if not self.station:
			return
		station = frappe.get_cached_doc("Station", self.station)
		self.dip_entry_mode = getattr(station, "dip_entry_mode", None) or "Litres"
		self.sales_basis = getattr(station, "sales_basis", None) or "Elec Cash"
		self.price_change_mode = getattr(station, "price_change_mode", None) or "Latest price"
		self.record_elec_cash = int(getattr(station, "record_elec_cash", 1) or 1)
		self.record_elec_meter = int(getattr(station, "record_elec_meter", 0) or 0)
		self.record_man_meter = int(getattr(station, "record_man_meter", 0) or 0)

	def _compute_shift_window(self) -> None:
		if not self.shift_template or not self.shift_date:
			return
		tpl = frappe.get_cached_doc("Forecourt Shift Template", self.shift_template)
		from datetime import date, datetime, time, timedelta

		def _combine(d, t) -> datetime:
			if isinstance(d, str):
				d = date.fromisoformat(d)
			if isinstance(t, str):
				h, m, s = [*t.split(":"), "0"][:3]
				t = time(int(h), int(m), int(float(s)))
			return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)

		if not self.shift_start:
			self.shift_start = _combine(self.shift_date, tpl.start_time)
		end_dt = _combine(self.shift_date, tpl.end_time)
		start_dt = get_datetime(self.shift_start)
		# overnight: end <= start means end is the next day
		if end_dt <= start_dt:
			end_dt = end_dt + timedelta(days=1)
		if not self.shift_end:
			self.shift_end = end_dt

	def _create_price_rows(self) -> None:
		if not self.station:
			return
		station = frappe.get_cached_doc("Station", self.station)
		price_list = getattr(station, "price_list", None)
		if not price_list:
			return

		fuel_items = frappe.get_all(
			"Item",
			filters={"fms_is_fuel": 1},
			fields=["name"],
		)
		for fuel in fuel_items:
			price = frappe.db.get_value(
				"Item Price",
				{"item_code": fuel.name, "price_list": price_list, "selling": 1},
				"price_list_rate",
			)
			if price:
				self.append(
					"prices",
					{
						"item": fuel.name,
						"segment_no": 1,
						"price": flt(price),
						"effective_from": self.shift_start,
						"effective_to": None,
					},
				)

	def _create_reading_rows(self) -> None:
		"""Create one Shift Meter Reading row per nozzle from the template."""
		if not self.shift_template:
			return
		tpl = frappe.get_cached_doc("Forecourt Shift Template", self.shift_template)
		station = frappe.get_cached_doc("Station", self.station) if self.station else None

		for nozzle_row in tpl.nozzle_assignments:
			nozzle = frappe.get_cached_doc("Nozzle", nozzle_row.nozzle)
			pump = frappe.get_cached_doc("Pump", nozzle.pump) if nozzle.pump else None

			rec_ecash = int(
				(getattr(pump, "record_elec_cash", None) if pump else None)
				or (getattr(station, "record_elec_cash", 1) or 1)
			)
			rec_evol = int(
				(getattr(pump, "record_elec_meter", None) if pump else None)
				or (getattr(station, "record_elec_meter", 0) or 0)
			)
			rec_mvol = int(
				(getattr(pump, "record_man_meter", None) if pump else None)
				or (getattr(station, "record_man_meter", 0) or 0)
			)
			sales_basis = (
				(getattr(pump, "sales_basis", None) if pump else None)
				or (getattr(station, "sales_basis", None) if station else None)
				or "Elec Cash"
			)

			price = self._get_price_for_item(nozzle.item) if nozzle.item else None

			self.append(
				"meter_readings",
				{
					"nozzle": nozzle_row.nozzle,
					"tank": nozzle.tank,
					"item": nozzle.item,
					"cashier": nozzle_row.cashier,
					"attendant": nozzle_row.attendant,
					"segment_no": 1,
					"price": flt(price) if price else 0.0,
					"rec_elec_cash": rec_ecash,
					"rec_elec_meter": rec_evol,
					"rec_man_meter": rec_mvol,
					"row_sales_basis": sales_basis,
					"opening_elec_cash": flt(nozzle.last_ecash),
					"opening_elec_meter": flt(nozzle.last_evol),
					"opening_man_meter": flt(nozzle.last_mvol),
					"source": "Manual",
				},
			)

	def _create_tank_rows(self) -> None:
		"""Create one Shift Tank Dip row per active tank at the station."""
		if not self.station:
			return
		tanks = frappe.get_all(
			"Fuel Tank",
			filters={"station": self.station, "status": "Active"},
			fields=["name", "item", "dip_entry_mode", "opening_dip_l"],
		)
		station = frappe.get_cached_doc("Station", self.station)
		station_dip_mode = getattr(station, "dip_entry_mode", "Litres") or "Litres"

		for tank in tanks:
			dip_mode = tank.dip_entry_mode or station_dip_mode
			opening_l = self._get_previous_closing_dip(tank.name)
			if opening_l is None:
				opening_l = flt(tank.opening_dip_l)

			self.append(
				"tank_dips",
				{
					"tank": tank.name,
					"item": tank.item,
					"dip_entry_mode": dip_mode,
					"opening_l": flt(opening_l),
					"source": "Manual",
				},
			)

	def _get_previous_closing_dip(self, tank: str) -> float | None:
		if not self.previous_shift:
			return None
		result = frappe.get_all(
			"Shift Tank Dip",
			filters={"parent": self.previous_shift, "tank": tank},
			fields=["dip_l"],
			limit=1,
		)
		return flt(result[0].dip_l) if result else None

	def _get_price_for_item(self, item: str) -> float | None:
		for row in self.prices:
			if row.item == item:
				return flt(row.price)
		return None

	def _set_title(self) -> None:
		if self.station and self.shift_template and self.shift_date:
			station_label = frappe.db.get_value("Station", self.station, "station_name") or self.station
			self.shift_title = f"{station_label} · {self.shift_template} · {self.shift_date}"


@frappe.whitelist()
def add_resolution(shift_name: str, resolution_for: str, ref: str) -> dict:
	"""Append a pre-filled resolution row to the shift and save.

	Called by the Resolve button on cashier and tank grid rows.
	Returns the new row's name so the client can navigate to it.
	"""
	shift = frappe.get_doc("Forecourt Shift", shift_name)
	frappe.has_permission("Forecourt Shift", doc=shift, throw=True)

	cashier = None
	tank = None
	action = "Charge to cashier"
	amount = 0.0
	volume_l = 0.0

	if resolution_for == "Cashier":
		cashier_row = next((c for c in shift.cashiers if c.cashier == ref), None)
		if not cashier_row:
			frappe.throw(_("Cashier {0} not found in this shift.").format(ref))
		diff = flt(cashier_row.difference, 2)
		cashier = ref
		if diff < 0:
			action = "Charge to cashier"
			amount = abs(diff)
		else:
			action = "Record excess"
			amount = diff
	elif resolution_for == "Tank":
		tank_row = next((t for t in shift.tank_dips if t.tank == ref), None)
		if not tank_row:
			frappe.throw(_("Tank {0} not found in this shift.").format(ref))
		tank = ref
		action = "Accept variance"
		volume_l = flt(tank_row.variance_l, 3)
	else:
		frappe.throw(_("Unknown resolution_for value: {0}").format(resolution_for))

	row = shift.append(
		"resolutions",
		{
			"resolution_for": resolution_for,
			"cashier": cashier,
			"tank": tank,
			"action": action,
			"amount": amount,
			"volume_l": volume_l,
		},
	)
	shift.flags.ignore_validate = True
	shift.save(ignore_permissions=True)
	return {"name": row.name, "action": action, "amount": amount, "volume_l": volume_l}


@frappe.whitelist()
def preview(shift_name: str) -> dict:
	"""Return a live calculation summary without saving.

	Called by the client script on every change to give instant feedback.
	Returns totals and per-cashier/per-tank summaries.
	"""
	doc = frappe.get_doc("Forecourt Shift", shift_name)
	doc.validate()
	return {
		"total_fuel_volume": doc.total_fuel_volume,
		"total_fuel_amount": doc.total_fuel_amount,
		"total_item_amount": doc.total_item_amount,
		"total_credit": doc.total_credit,
		"total_mobile": doc.total_mobile,
		"total_card": doc.total_card,
		"total_cash": doc.total_cash,
		"total_expenses": doc.total_expenses,
		"total_difference": doc.total_difference,
		"total_tank_variance_l": doc.total_tank_variance_l,
		"cashiers": [
			{
				"cashier": r.cashier,
				"expected": r.expected,
				"accounted": r.accounted,
				"difference": r.difference,
			}
			for r in doc.cashiers
		],
		"tank_dips": [
			{
				"tank": r.tank,
				"expected_l": r.expected_l,
				"variance_l": r.variance_l,
				"variance_pct": r.variance_pct,
				"within_tolerance": r.within_tolerance,
			}
			for r in doc.tank_dips
		],
	}
