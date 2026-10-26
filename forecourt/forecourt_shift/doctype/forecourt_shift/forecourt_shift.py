"""Forecourt Shift controller.

F01: DocType structure.
F02: before_insert pre-fill.
F03: validate calculations.
F04: meter modes/drift gate.
F05: pull GRN receipts and own use into tank dip rows; chart-mode dip.
F06: pull own use into meter reading rows; FMS-S113 draft own-use gate.
F12+: remaining before_submit gates (added in later tasks).
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
from forecourt.errors import FMS_S113, FMS_W103


class ForecourtShift(Document):
	# ------------------------------------------------------------------ F04 / F06
	def before_submit(self) -> None:
		"""Gates: FMS-W103 drift reason; FMS-S113 no draft own use in window."""
		self._gate_drift_reason()
		self._gate_no_draft_own_use()

	def _gate_drift_reason(self) -> None:
		settings = frappe.get_cached_doc("Forecourt Settings")
		if not getattr(settings, "drift_requires_reason", True):
			return
		missing = [row.nozzle for row in self.meter_readings if row.drift_breach and not row.drift_reason]
		if missing:
			frappe.throw(
				_("{0}: Drift beyond tolerance on {1} — record the reason before closing.").format(
					FMS_W103, ", ".join(missing)
				),
				title=_("Drift Reason Required"),
			)

	def _gate_no_draft_own_use(self) -> None:
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
			frappe.throw(
				_(
					"{0}: Draft Fuel Own Use entries exist in the shift window: {1}. Submit or delete them before closing."
				).format(FMS_S113, ", ".join(blocking)),
				title=_("Draft Own Use Entry"),
			)

	# ------------------------------------------------------------------ F03 / F05 / F06
	def validate(self) -> None:
		self._compute_item_sale_amounts()
		self._pull_own_use_for_nozzles()  # F06: own use → meter rows
		self._compute_meter_rows()
		self._compute_dip_volumes()  # F05: chart-mode mm→L
		self._pull_grn_receipts()  # F05: receipts from submitted GRNs
		self._pull_own_use_for_tanks()  # F05: own use into tank rows
		self._compute_tank_dip_rows()
		self._compute_cashier_rows()
		self._compute_parent_totals()

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
