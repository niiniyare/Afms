"""Opening balances: single authoritative source, server-side immutability, sales bases.

Integration tests (need a bench site). Regression for the field defect where a new shift
took meter openings from Nozzle.last_* (updated by shift 00075) but tank openings from the
draft shift 00076.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import flt

from forecourt.forecourt_shift import openings as shift_openings
from forecourt.setup.default_accounts import create_default_accounts
from forecourt.tests.factories import (
	FMSTestCase,
	make_fuel_item,
	make_fuel_tank,
	make_nozzle,
	make_pump,
	make_station,
	map_company_settings_to_defaults,
)
from forecourt.tests.test_golden_mvp import _make_employee

_OPEN_DRAFTS = "forecourt.forecourt_shift.openings.open_drafts"


class _Base(FMSTestCase):
	"""Station with two tanks, two nozzles and one template; helpers to fabricate shifts."""

	CODE = "KE-OB-TEST"
	BASIS = "Elec Cash"

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls._build_fixtures()

	def setUp(self) -> None:
		super().setUp()
		frappe.db.savepoint("fms_ob")

	def tearDown(self) -> None:
		frappe.db.rollback(save_point="fms_ob")
		super().tearDown()

	@classmethod
	def _build_fixtures(cls) -> None:
		self = cls
		self.company = frappe.defaults.get_defaults().get("company") or "_Test Company"
		self.currency = frappe.db.get_value("Company", self.company, "default_currency") or "USD"
		self.accounts = create_default_accounts(self.company)
		map_company_settings_to_defaults(self.company, self.accounts)
		frappe.clear_document_cache("Forecourt Company Settings", self.company)
		self.emp = _make_employee(f"Opening {self.CODE}", self.company)

		self.station = make_station(
			code=self.CODE,
			company=self.company,
			safe_account=self.accounts["safe"],
			till_accounts=[{"currency": self.currency, "account": self.accounts["till"]}],
			sales_basis=self.BASIS,
			record_elec_cash=1,
			record_elec_meter=1,
			record_man_meter=1,
		)
		self.pms = make_fuel_item(f"{self.CODE}-PMS", item_name="PMS", stock_uom="Litre")
		self.ago = make_fuel_item(f"{self.CODE}-AGO", item_name="AGO", stock_uom="Litre")
		self.t_pms = make_fuel_tank(
			station=self.station.name, tank_code="T-PMS", item=self.pms.name, opening_dip_l=8000
		)
		self.t_ago = make_fuel_tank(
			station=self.station.name, tank_code="T-AGO", item=self.ago.name, opening_dip_l=5200
		)
		pump = make_pump(station=self.station.name, pump_code="P01")
		self.n1 = make_nozzle(
			pump=pump.name,
			tank=self.t_pms.name,
			nozzle_no=1,
			opening_date="2026-10-01",
			opening_ecash=10000,
			opening_evol=100,
			opening_mvol=100,
		)
		self.n2 = make_nozzle(
			pump=pump.name,
			tank=self.t_ago.name,
			nozzle_no=2,
			opening_date="2026-10-01",
			opening_ecash=5000,
			opening_evol=50,
			opening_mvol=50,
		)
		tmpl = frappe.get_doc(
			{
				"doctype": "Forecourt Shift Template",
				"station": self.station.name,
				"template_name": f"Day-{self.CODE}",
				"start_time": "06:00:00",
				"end_time": "18:00:00",
				"nozzle_assignments": [
					{"nozzle": self.n1.name, "cashier": self.emp},
					{"nozzle": self.n2.name, "cashier": self.emp},
				],
			}
		)
		tmpl.flags.ignore_permissions = True
		tmpl.insert()
		self.tmpl = tmpl

	# ---- helpers ---------------------------------------------------------

	def new_shift(self, shift_date: str, allow_open_drafts: bool = False):
		doc = frappe.get_doc(
			{
				"doctype": "Forecourt Shift",
				"station": self.station.name,
				"company": self.company,
				"shift_template": self.tmpl.name,
				"shift_date": shift_date,
				"prices": [
					{"item": self.pms.name, "price": 180},
					{"item": self.ago.name, "price": 170},
				],
			}
		)
		doc.flags.ignore_permissions = True
		if allow_open_drafts:
			with patch(_OPEN_DRAFTS, return_value=[]):
				doc.insert()
		else:
			doc.insert()
		return doc

	def fake_submit(self, shift, closings: dict[str, float], dips: dict[str, float]) -> None:
		"""Set closing readings and mark the shift submitted (test data only)."""
		for row in shift.meter_readings:
			if row.nozzle in closings:
				frappe.db.set_value(
					"Shift Meter Reading", row.name, "closing_elec_cash", closings[row.nozzle]
				)
		for row in shift.tank_dips:
			if row.tank in dips:
				frappe.db.set_value("Shift Tank Dip", row.name, "dip_l", dips[row.tank])
		frappe.db.set_value("Forecourt Shift", shift.name, {"docstatus": 1, "status": "Closed"})

	def meter(self, shift, nozzle: str):
		return next(r for r in shift.meter_readings if r.nozzle == nozzle)

	def tank(self, shift, tank: str):
		return next(r for r in shift.tank_dips if r.tank == tank)


class TestOpeningSource(_Base):
	def test_first_shift_uses_configured_initial_readings(self) -> None:
		s = self.new_shift("2026-11-01")
		self.assertIsNone(s.previous_shift)
		self.assertEqual(flt(self.meter(s, self.n1.name).opening_elec_cash), 10000)
		self.assertEqual(flt(self.meter(s, self.n1.name).opening_elec_meter), 100)
		self.assertEqual(flt(self.meter(s, self.n2.name).opening_elec_cash), 5000)
		self.assertEqual(flt(self.tank(s, self.t_pms.name).opening_l), 8000)
		self.assertEqual(flt(self.tank(s, self.t_ago.name).opening_l), 5200)

	def test_meter_and_tank_openings_share_one_source_with_stale_draft(self) -> None:
		"""00075 submitted -> draft 00076 -> 00077: openings must come from 00075 only."""
		a = self.new_shift("2026-11-01")
		self.fake_submit(
			a,
			{self.n1.name: 12000, self.n2.name: 6000},
			{self.t_pms.name: 7000, self.t_ago.name: 4800},
		)
		# Simulate stale Nozzle.last_* left by 00075 and a different draft 00076.
		frappe.db.set_value("Nozzle", self.n1.name, "last_ecash", 12000)
		b = self.new_shift("2026-11-02")
		self.assertEqual(b.previous_shift, a.name)
		frappe.db.set_value("Shift Tank Dip", self.tank(b, self.t_pms.name).name, "dip_l", 777)
		frappe.db.set_value(
			"Shift Meter Reading", self.meter(b, self.n1.name).name, "closing_elec_cash", 99999
		)

		c = self.new_shift("2026-11-03", allow_open_drafts=True)  # legacy: two drafts coexist

		self.assertEqual(c.previous_shift, a.name)
		self.assertEqual(flt(self.meter(c, self.n1.name).opening_elec_cash), 12000)
		self.assertEqual(flt(self.meter(c, self.n2.name).opening_elec_cash), 6000)
		self.assertEqual(flt(self.tank(c, self.t_pms.name).opening_l), 7000)
		self.assertEqual(flt(self.tank(c, self.t_ago.name).opening_l), 4800)

	def test_cancelled_shift_never_used(self) -> None:
		a = self.new_shift("2026-11-01")
		self.fake_submit(
			a, {self.n1.name: 12000, self.n2.name: 6000}, {self.t_pms.name: 7000, self.t_ago.name: 4800}
		)
		b = self.new_shift("2026-11-02")
		self.fake_submit(
			b, {self.n1.name: 15000, self.n2.name: 9000}, {self.t_pms.name: 3000, self.t_ago.name: 2000}
		)
		frappe.db.set_value("Forecourt Shift", b.name, "docstatus", 2)
		c = self.new_shift("2026-11-03")
		self.assertEqual(c.previous_shift, a.name)
		self.assertEqual(flt(self.meter(c, self.n1.name).opening_elec_cash), 12000)
		self.assertEqual(flt(self.tank(c, self.t_pms.name).opening_l), 7000)

	def test_nozzle_absent_from_previous_shift_uses_configured_initial(self) -> None:
		a = self.new_shift("2026-11-01")
		self.fake_submit(a, {self.n1.name: 12000, self.n2.name: 6000}, {})
		pump = make_pump(station=self.station.name, pump_code="P02")
		n3 = make_nozzle(
			pump=pump.name, tank=self.t_pms.name, nozzle_no=1, opening_date="2026-11-01", opening_ecash=777
		)
		out = shift_openings.nozzle_openings(n3.name, a.name)
		self.assertEqual(out["opening_elec_cash"], 777)

	def test_api_supplied_openings_are_overridden_at_insert(self) -> None:
		doc = frappe.get_doc(
			{
				"doctype": "Forecourt Shift",
				"station": self.station.name,
				"company": self.company,
				"shift_template": self.tmpl.name,
				"shift_date": "2026-11-01",
				"prices": [{"item": self.pms.name, "price": 180}, {"item": self.ago.name, "price": 170}],
				"meter_readings": [
					{
						"nozzle": self.n1.name,
						"tank": self.t_pms.name,
						"item": self.pms.name,
						"cashier": self.emp,
						"rec_elec_cash": 1,
						"opening_elec_cash": 1,
						"closing_elec_cash": 1,
						"price": 180,
					}
				],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		rows = [r for r in doc.meter_readings if r.nozzle == self.n1.name and (r.segment_no or 1) == 1]
		self.assertTrue(rows)
		for r in rows:
			self.assertEqual(flt(r.opening_elec_cash), 10000)


class TestOpeningImmutable(_Base):
	CODE = "KE-OB-LOCK"

	def setUp(self) -> None:
		super().setUp()
		self.shift = self.new_shift("2026-11-01")

	def _assert_locked(self, fn) -> None:
		with self.assertRaises(frappe.ValidationError) as ctx:
			fn()
		self.assertIn("FMS-S121", str(ctx.exception))

	def test_edit_meter_opening_via_document_save(self) -> None:
		doc = frappe.get_doc("Forecourt Shift", self.shift.name)
		doc.meter_readings[0].opening_elec_cash = 1
		self._assert_locked(doc.save)

	def test_edit_tank_opening_via_document_save(self) -> None:
		doc = frappe.get_doc("Forecourt Shift", self.shift.name)
		doc.tank_dips[0].opening_l = 1
		self._assert_locked(doc.save)

	def test_edit_via_client_set_value_on_child_row(self) -> None:
		row = self.meter(self.shift, self.n1.name)
		self._assert_locked(
			lambda: frappe.client.set_value("Shift Meter Reading", row.name, "opening_elec_cash", 5)
		)
		trow = self.tank(self.shift, self.t_pms.name)
		self._assert_locked(lambda: frappe.client.set_value("Shift Tank Dip", trow.name, "opening_l", 5))

	def test_edit_via_client_save_payload(self) -> None:
		payload = frappe.get_doc("Forecourt Shift", self.shift.name).as_dict()
		payload["meter_readings"][0]["opening_elec_meter"] = 123456
		self._assert_locked(lambda: frappe.client.save(payload))

	def test_delete_and_readd_row_with_new_opening(self) -> None:
		doc = frappe.get_doc("Forecourt Shift", self.shift.name)
		old = self.meter(doc, self.n1.name)
		doc.remove(old)
		doc.append(
			"meter_readings",
			{
				"nozzle": self.n1.name,
				"tank": self.t_pms.name,
				"item": self.pms.name,
				"cashier": self.emp,
				"segment_no": 1,
				"rec_elec_cash": 1,
				"opening_elec_cash": 42,
				"closing_elec_cash": 100,
				"price": 180,
			},
		)
		self._assert_locked(doc.save)

	def test_duplicate_row_with_new_opening(self) -> None:
		doc = frappe.get_doc("Forecourt Shift", self.shift.name)
		src = self.meter(doc, self.n1.name)
		dup = src.as_dict()
		dup.pop("name", None)
		dup["opening_elec_cash"] = 3
		doc.append("meter_readings", dup)
		self._assert_locked(doc.save)

	def test_replace_tank_row_with_new_opening(self) -> None:
		doc = frappe.get_doc("Forecourt Shift", self.shift.name)
		old = self.tank(doc, self.t_pms.name)
		doc.remove(old)
		doc.append("tank_dips", {"tank": self.t_pms.name, "item": self.pms.name, "opening_l": 1, "dip_l": 1})
		self._assert_locked(doc.save)

	def test_change_previous_shift(self) -> None:
		other = self.new_shift("2026-11-02", allow_open_drafts=True)
		doc = frappe.get_doc("Forecourt Shift", self.shift.name)
		doc.previous_shift = other.name
		self._assert_locked(doc.save)

	def test_closing_readings_remain_editable(self) -> None:
		doc = frappe.get_doc("Forecourt Shift", self.shift.name)
		self.meter(doc, self.n1.name).closing_elec_cash = 10500
		self.tank(doc, self.t_pms.name).dip_l = 7900
		doc.save()
		doc.reload()
		self.assertEqual(flt(self.meter(doc, self.n1.name).closing_elec_cash), 10500)
		self.assertEqual(flt(self.meter(doc, self.n1.name).opening_elec_cash), 10000)
		self.assertEqual(flt(self.tank(doc, self.t_pms.name).opening_l), 8000)


class TestSalesBasisEndToEnd(_Base):
	"""Every basis offered in Station/Pump setup must reconcile, submit and post."""

	CODE = "KE-OB-BASIS"

	def _run_basis(self, basis: str, expected_ledger_basis: str) -> None:
		frappe.db.set_value("Station", self.station.name, "sales_basis", basis)
		orig = frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0
		frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
		try:
			shift = self.new_shift("2026-11-24")
			# 700 L PMS @180 = 126000 KES on N1; N2 idle.
			r1 = self.meter(shift, self.n1.name)
			r1.closing_elec_cash = 10000 + 126000
			r1.closing_elec_meter = 100 + 700
			r1.closing_man_meter = 100 + 700
			r1.row_sales_basis = basis
			self.meter(shift, self.n2.name).row_sales_basis = basis
			self.tank(shift, self.t_pms.name).dip_l = 8000 - 700
			shift.append(
				"cash_counts",
				{
					"cashier": self.emp,
					"currency": self.currency,
					"amount": 126000,
					"base_amount": 126000,
				},
			)
			shift.flags.ignore_permissions = True
			shift.save()
			shift.reconcile()
			shift.reload()
			shift.submit()
			self.assertEqual(frappe.db.get_value("Forecourt Shift", shift.name, "status"), "Closed")
			nle = frappe.get_all(
				"Nozzle Ledger Entry",
				filters={"forecourt_shift": shift.name, "nozzle": self.n1.name},
				fields=["basis_meter", "net_l"],
			)
			self.assertEqual(len(nle), 1)
			self.assertEqual(nle[0].basis_meter, expected_ledger_basis)
			self.assertAlmostEqual(flt(nle[0].net_l), 700, places=2)
		finally:
			frappe.db.set_single_value("Stock Settings", "allow_negative_stock", orig)

	def test_basis_elec_cash(self) -> None:
		self._run_basis("Elec Cash", "Elec Cash")

	def test_basis_elec_mtr(self) -> None:
		self._run_basis("Elec Mtr", "Elec Mtr")

	def test_basis_man_mtr(self) -> None:
		self._run_basis("Man Mtr", "Man Mtr")

	def test_basis_highest(self) -> None:
		self._run_basis("Highest", "Highest")

	def test_setup_options_match_ledger_options(self) -> None:
		"""Every basis offered on Station / Pump is accepted by the Nozzle Ledger Entry."""

		def opts(dt: str, field: str) -> set[str]:
			return {o for o in (frappe.get_meta(dt).get_field(field).options or "").split("\n") if o}

		ledger = opts("Nozzle Ledger Entry", "basis_meter")
		for dt, field in (("Station", "sales_basis"), ("Pump", "sales_basis")):
			offered = opts(dt, field)
			self.assertTrue(offered, f"{dt}.{field} has no options")
			self.assertTrue(
				offered <= ledger, f"{dt}.{field} offers {offered - ledger} not accepted by ledger"
			)


class TestAbandonDraft(_Base):
	CODE = "KE-OB-ABN"

	def _make_user(self, email: str, roles: list[str]) -> str:
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Abandon",
					"send_welcome_email": 0,
					"roles": [{"role": r} for r in roles],
				}
			).insert(ignore_permissions=True)
		return email

	def _abandon(self, shift, reason: str = "Created by mistake, never used"):
		from forecourt.forecourt_shift.doctype.forecourt_shift.forecourt_shift import abandon_draft

		return abandon_draft(shift.name, reason)

	def test_s116_message_lists_every_draft(self) -> None:
		d1 = self.new_shift("2026-11-01")
		d2 = self.new_shift("2026-11-02", allow_open_drafts=True)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.new_shift("2026-11-03")
		msg = str(ctx.exception)
		self.assertIn("FMS-S116", msg)
		self.assertIn(d1.name, msg)
		self.assertIn(d2.name, msg)

	def test_abandon_preserves_data_and_unblocks_new_shift(self) -> None:
		d1 = self.new_shift("2026-11-01")
		rows_before = len(d1.meter_readings)
		out = self._abandon(d1)
		self.assertEqual(out["status"], "Abandoned")
		row = frappe.db.get_value(
			"Forecourt Shift",
			d1.name,
			["status", "docstatus", "abandoned_by", "abandoned_at", "abandon_reason"],
			as_dict=True,
		)
		self.assertEqual((row.status, row.docstatus), ("Abandoned", 0))
		self.assertEqual(row.abandoned_by, frappe.session.user)
		self.assertTrue(row.abandoned_at)
		self.assertIn("never used", row.abandon_reason)
		self.assertEqual(frappe.db.count("Shift Meter Reading", {"parent": d1.name}), rows_before)
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{"reference_doctype": "Forecourt Shift", "reference_name": d1.name, "comment_type": "Info"},
			)
		)
		self.assertEqual(shift_openings.open_drafts(self.station.name), [])
		self.new_shift("2026-11-02")  # no S116 any more

	def test_abandoned_shift_cannot_be_edited_or_submitted(self) -> None:
		d1 = self.new_shift("2026-11-01")
		self._abandon(d1)
		doc = frappe.get_doc("Forecourt Shift", d1.name)
		doc.remarks = "edit"
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.save()
		self.assertIn("FMS-S122", str(ctx.exception))
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.get_doc("Forecourt Shift", d1.name).submit()
		self.assertIn("FMS-S122", str(ctx.exception))

	def test_status_cannot_be_set_to_abandoned_by_plain_save(self) -> None:
		d1 = self.new_shift("2026-11-01")
		doc = frappe.get_doc("Forecourt Shift", d1.name)
		doc.status = "Abandoned"
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.save()
		self.assertIn("FMS-S122", str(ctx.exception))

	def test_refuses_submitted_and_double_abandon_and_short_reason(self) -> None:
		d1 = self.new_shift("2026-11-01")
		with self.assertRaises(frappe.ValidationError):
			self._abandon(d1, "short")
		self._abandon(d1)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._abandon(d1)
		self.assertIn("already abandoned", str(ctx.exception))
		d2 = self.new_shift("2026-11-02")
		frappe.db.set_value("Forecourt Shift", d2.name, "docstatus", 1)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._abandon(d2)
		self.assertIn("FMS-S122", str(ctx.exception))

	def test_refuses_closing_shift(self) -> None:
		d1 = self.new_shift("2026-11-01")
		frappe.db.set_value("Forecourt Shift", d1.name, "status", "Closing")
		with self.assertRaises(frappe.ValidationError):
			self._abandon(d1)

	def test_refuses_when_native_document_linked(self) -> None:
		d1 = self.new_shift("2026-11-01")
		real_get_all = frappe.get_all

		def fake_get_all(doctype, *a, **kw):
			if doctype == "Stock Entry" and (kw.get("filters") or {}).get("fms_forecourt_shift") == d1.name:
				return ["MAT-STE-TEST-0001"]
			return real_get_all(doctype, *a, **kw)

		with patch("frappe.get_all", side_effect=fake_get_all):
			with self.assertRaises(frappe.ValidationError) as ctx:
				self._abandon(d1)
		self.assertIn("MAT-STE-TEST-0001", str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Forecourt Shift", d1.name, "status"), "Open")

	def test_unauthorised_role_refused(self) -> None:
		d1 = self.new_shift("2026-11-01")
		user = self._make_user("abandon.cashier@example.com", ["Supervisor"])
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				self._abandon(d1)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Forecourt Shift", d1.name, "status"), "Open")
