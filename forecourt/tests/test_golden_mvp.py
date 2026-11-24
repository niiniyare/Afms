"""Golden scenario integration test — FMS MVP.

Two cashiers, four nozzles, one credit customer, one staff shortage.

Station: KE-GOLD-TEST
  PMS  Amina  N1 (opening 10000, closing 10700) + N2 (5000→5500)
  AGO  Brian  N3 (opening 20000, closing 20500) + N4 (25000→25400)
  Credit: Coast Haulage, 200 L AGO via N3, slip CS-001
  Brian shortage: -500 -> Charge to cashier

Acceptance criteria
  1. PMS warehouse stock  = 6 780 L (from dip)
  2. AGO warehouse stock  = 4 290 L (from dip)
  3. Coast Haulage AR     = 34 000 (outstanding on credit SI)
  4. Staff shortage JE    exists, DR=500 to FMS Staff Shortage Payable
  5. Walk-in Sales Invoice exists, grand_total > 0
  6. Credit Sales Invoice  exists for Coast Haulage
  7. NLE = 4, WLE = 2, CLE = 2 (MVP ledgers only; SLE not written)
  8. Shift status = "Closed"
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from forecourt.setup.default_accounts import create_default_accounts
from forecourt.tests.factories import (
	FMSTestCase,
	make_fuel_item,
	make_fuel_tank,
	make_nozzle,
	make_pump,
	make_station,
	make_station_group,
)


class TestGoldenMVP(FMSTestCase):
	"""Full-stack shift submission test against the MVP spec golden scenario."""

	def test_golden_mvp_scenario(self) -> None:
		company = frappe.defaults.get_defaults().get("company") or "_Test Company"
		currency = frappe.db.get_value("Company", company, "default_currency") or "USD"

		# ── 1. FMS accounts + FCS + Modes of Payment ─────────────────────────
		accounts = create_default_accounts(company)
		frappe.clear_document_cache("Forecourt Company Settings", company)

		# ── 2. Variance Reason (required on Shift Resolution) ─────────────────
		reason_doc = frappe.get_doc(
			{
				"doctype": "Variance Reason",
				"reason": "Staff Shortage Test",
				"applies_to_cashier": 1,
			}
		)
		reason_doc.flags.ignore_permissions = True
		reason_doc.insert()

		# ── 3. Employees ──────────────────────────────────────────────────────
		amina_id = _make_employee("Amina Gold", company)
		brian_id = _make_employee("Brian Gold", company)

		# ── 4. Credit customer ────────────────────────────────────────────────
		_make_customer("Coast Haulage Gold")

		# ── 5. Station (uses FMS accounts) ───────────────────────────────────
		station = make_station(
			code="KE-GOLD-TEST",
			company=company,
			safe_account=accounts["safe"],
			till_accounts=[{"currency": currency, "account": accounts["till"]}],
		)

		# ── 6. Fuel items ─────────────────────────────────────────────────────
		pms = make_fuel_item("GOLD-PMS", item_name="Gold PMS", stock_uom="Litre")
		ago = make_fuel_item("GOLD-AGO", item_name="Gold AGO", stock_uom="Litre")

		# ── 7. Tanks → warehouses auto-created by Fuel Tank controller ────────
		pms_tank = make_fuel_tank(station=station.name, tank_code="T-PMS", item=pms.name)
		ago_tank = make_fuel_tank(station=station.name, tank_code="T-AGO", item=ago.name)

		# ── 8. Pumps + nozzles ────────────────────────────────────────────────
		p1 = make_pump(station=station.name, pump_code="P01")
		p2 = make_pump(station=station.name, pump_code="P02")

		n1 = make_nozzle(pump=p1.name, tank=pms_tank.name, nozzle_no=1)
		n2 = make_nozzle(pump=p1.name, tank=pms_tank.name, nozzle_no=2)
		n3 = make_nozzle(pump=p2.name, tank=ago_tank.name, nozzle_no=1)
		n4 = make_nozzle(pump=p2.name, tank=ago_tank.name, nozzle_no=2)

		# ── 9. Shift Template (required field) ────────────────────────────────
		tmpl = frappe.get_doc(
			{
				"doctype": "Forecourt Shift Template",
				"station": station.name,
				"template_name": "Day-Gold",
				"start_time": "06:00:00",
				"end_time": "18:00:00",
			}
		)
		tmpl.flags.ignore_permissions = True
		tmpl.insert()

		# ── 10. Allow negative stock for the duration of the test ─────────────
		orig_neg_stock = frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0
		frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
		try:
			self._submit_shift_and_assert(
				company=company,
				currency=currency,
				station=station,
				pms=pms,
				ago=ago,
				pms_tank=pms_tank,
				ago_tank=ago_tank,
				n1=n1,
				n2=n2,
				n3=n3,
				n4=n4,
				tmpl=tmpl,
				amina_id=amina_id,
				brian_id=brian_id,
				reason_name=reason_doc.name,
				accounts=accounts,
			)
		finally:
			frappe.db.set_single_value("Stock Settings", "allow_negative_stock", orig_neg_stock)

	# ── implementation ────────────────────────────────────────────────────────

	def _submit_shift_and_assert(
		self,
		company,
		currency,
		station,
		pms,
		ago,
		pms_tank,
		ago_tank,
		n1,
		n2,
		n3,
		n4,
		tmpl,
		amina_id,
		brian_id,
		reason_name,
		accounts,
	) -> None:
		shift = frappe.get_doc(
			{
				"doctype": "Forecourt Shift",
				"station": station.name,
				"company": company,
				"shift_template": tmpl.name,
				"shift_date": "2026-11-24",
				"shift_start": "2026-11-24 06:00:00",
				"shift_end": "2026-11-24 18:00:00",
				# Prices
				"prices": [
					{"item": pms.name, "price": 180},
					{"item": ago.name, "price": 170},
				],
				# Meter readings — E-cash meter is MONETARY (KES), not litres.
				# closing = opening + (volume_L x price).
				# N1: 700 L x 180 = 126 000  -> closing = 10 000 + 126 000 = 136 000
				# N2: 500 L x 180 =  90 000  -> closing =  5 000 +  90 000 =  95 000
				# N3: 500 L x 170 =  85 000  -> closing = 20 000 +  85 000 = 105 000
				# N4: 400 L x 170 =  68 000  -> closing = 25 000 +  68 000 =  93 000
				"meter_readings": [
					{
						"nozzle": n1.name,
						"tank": pms_tank.name,
						"item": pms.name,
						"cashier": amina_id,
						"rec_elec_cash": 1,
						"opening_elec_cash": 10000,
						"closing_elec_cash": 136000,
						"price": 180,
					},
					{
						"nozzle": n2.name,
						"tank": pms_tank.name,
						"item": pms.name,
						"cashier": amina_id,
						"rec_elec_cash": 1,
						"opening_elec_cash": 5000,
						"closing_elec_cash": 95000,
						"price": 180,
					},
					{
						"nozzle": n3.name,
						"tank": ago_tank.name,
						"item": ago.name,
						"cashier": brian_id,
						"rec_elec_cash": 1,
						"opening_elec_cash": 20000,
						"closing_elec_cash": 105000,
						"price": 170,
					},
					{
						"nozzle": n4.name,
						"tank": ago_tank.name,
						"item": ago.name,
						"cashier": brian_id,
						"rec_elec_cash": 1,
						"opening_elec_cash": 25000,
						"closing_elec_cash": 93000,
						"price": 170,
					},
				],
				# Tank dips omitted here — before_insert auto-creates one row per
				# active tank.  We update opening_l / dip_l after insert() below.
				# Cashiers
				"cashiers": [
					{"cashier": amina_id, "float_amount": 2000},
					{"cashier": brian_id, "float_amount": 3000},
				],
				# Cash counts
				"cash_counts": [
					{
						"cashier": amina_id,
						"currency": currency,
						"amount": 98000,
						"base_amount": 98000,
					},
					{
						"cashier": brian_id,
						"currency": currency,
						"amount": 21500,
						"base_amount": 21500,
					},
				],
				# Collections (unique reference per provider, cross-shift)
				"collections": [
					{
						"cashier": amina_id,
						"collection_type": "Mobile Money",
						"mode_of_payment": "Mobile Money",
						"amount": 100000,
						"reference": "GOLD-MM-A-001",
					},
					{
						"cashier": amina_id,
						"collection_type": "Card",
						"mode_of_payment": "Card",
						"amount": 20000,
						"reference": "GOLD-CARD-A-001",
					},
					{
						"cashier": brian_id,
						"collection_type": "Mobile Money",
						"mode_of_payment": "Mobile Money",
						"amount": 80000,
						"reference": "GOLD-MM-B-001",
					},
					{
						"cashier": brian_id,
						"collection_type": "Card",
						"mode_of_payment": "Card",
						"amount": 20000,
						"reference": "GOLD-CARD-B-001",
					},
				],
				# Credit sales (Brian, Coast Haulage, 200 L AGO via N3)
				"credit_sales": [
					{
						"cashier": brian_id,
						"customer": "Coast Haulage Gold",
						"item": ago.name,
						"nozzle": n3.name,
						"qty": 200,
						"rate": 170,
						"amount": 34000,
						"slip_no": "CS-001",
						"sold_at": "2026-11-24 10:00:00",
					}
				],
				# Resolution: Brian -500 -> Charge to cashier
				"resolutions": [
					{
						"resolution_for": "Cashier",
						"cashier": brian_id,
						"action": "Charge to cashier",
						"amount": 500,
						"reason": reason_name,
					}
				],
			}
		)

		shift.flags.ignore_permissions = True
		shift.insert()

		# Set tank dip values on the auto-created rows (before_insert created them
		# with opening_l = 0 / dip_l = 0 since no previous shift exists).
		for row in shift.tank_dips:
			if row.tank == pms_tank.name:
				row.opening_l = 8000
				row.dip_l = 6780
			elif row.tank == ago_tank.name:
				row.opening_l = 5200
				row.dip_l = 4290
		shift.flags.ignore_permissions = True
		shift.save()

		# Reconcile (sets status = "Reconciled")
		shift.reconcile()

		# Submit (runs before_submit gates + on_submit posting chain)
		shift.reload()
		shift.submit()

		# ── Assertions ────────────────────────────────────────────────────────

		# 8. Status = Closed
		self.assertEqual(
			frappe.db.get_value("Forecourt Shift", shift.name, "status"),
			"Closed",
			"Shift status must be Closed after submission",
		)

		# 7. MVP ledger counts (SLE must NOT be written)
		self.assertEqual(
			frappe.db.count("Nozzle Ledger Entry", {"forecourt_shift": shift.name}),
			4,
			"Expected 4 Nozzle Ledger Entries (one per meter reading row)",
		)
		self.assertEqual(
			frappe.db.count("Wetstock Ledger Entry", {"forecourt_shift": shift.name}),
			2,
			"Expected 2 Wetstock Ledger Entries (one per tank dip)",
		)
		self.assertEqual(
			frappe.db.count("Cashier Ledger Entry", {"forecourt_shift": shift.name}),
			2,
			"Expected 2 Cashier Ledger Entries (one per cashier)",
		)
		self.assertEqual(
			frappe.db.count("Sales Ledger Entry", {"forecourt_shift": shift.name}),
			0,
			"Sales Ledger Entries must NOT be written (MVP SLE deferred)",
		)

		# 1 & 2. Tank stock after Stock Reconciliation
		# Query at shift_end so we see the SR that posts at that time (not at
		# today's current clock time, which may be earlier than the fictional shift).
		from erpnext.stock.utils import get_stock_balance

		pms_wh = frappe.db.get_value("Fuel Tank", pms_tank.name, "warehouse")
		ago_wh = frappe.db.get_value("Fuel Tank", ago_tank.name, "warehouse")

		pms_stock = get_stock_balance(pms.name, pms_wh, "2026-11-24", "18:00:00")
		ago_stock = get_stock_balance(ago.name, ago_wh, "2026-11-24", "18:00:00")

		self.assertAlmostEqual(pms_stock, 6780, delta=0.001, msg="PMS stock must equal closing dip")
		self.assertAlmostEqual(ago_stock, 4290, delta=0.001, msg="AGO stock must equal closing dip")

		# 5. Walk-in Sales Invoice
		# walk_in_customer is set via db.set_value in after_insert, reload to get it.
		walk_in_customer = frappe.db.get_value("Station", station.name, "walk_in_customer")
		walkin_si_name = frappe.db.get_value(
			"Sales Invoice",
			{
				"fms_forecourt_shift": shift.name,
				"customer": walk_in_customer,
				"docstatus": 1,
				"is_return": 0,
			},
			"name",
		)
		self.assertIsNotNone(walkin_si_name, "Walk-in Sales Invoice not found")
		walkin_total = frappe.db.get_value("Sales Invoice", walkin_si_name, "grand_total")
		self.assertGreater(flt(walkin_total), 0, "Walk-in SI grand_total must be > 0")

		# 6. Credit Sales Invoice for Coast Haulage
		credit_si_name = frappe.db.get_value(
			"Sales Invoice",
			{
				"fms_forecourt_shift": shift.name,
				"customer": "Coast Haulage Gold",
				"docstatus": 1,
			},
			"name",
		)
		self.assertIsNotNone(credit_si_name, "Coast Haulage credit Sales Invoice not found")

		# 3. Coast Haulage AR = 34 000
		outstanding = flt(frappe.db.get_value("Sales Invoice", credit_si_name, "outstanding_amount"))
		self.assertAlmostEqual(
			outstanding,
			34000,
			delta=1,
			msg="Coast Haulage outstanding AR must be ~34 000",
		)

		# 4. Brian shortage JE: DR FMS Staff Shortage Payable 500, CR till 500
		je_name = frappe.db.get_value(
			"Journal Entry",
			{"fms_forecourt_shift": shift.name, "docstatus": 1},
			"name",
		)
		self.assertIsNotNone(je_name, "Journal Entry for shortage not found")

		je_doc = frappe.get_doc("Journal Entry", je_name)
		shortage_entry = next(
			(
				a
				for a in je_doc.accounts
				if a.account == accounts["staff_shortage"]
				and flt(a.debit_in_account_currency) == 500
				and a.party == brian_id
			),
			None,
		)
		self.assertIsNotNone(
			shortage_entry,
			"Staff shortage JE row (DR=500, party=Brian) not found in Journal Entry",
		)


# ── local test helpers ────────────────────────────────────────────────────────


def _make_employee(employee_name: str, company: str) -> str:
	"""Create a minimal Employee; return its name (auto-generated ID)."""
	existing = frappe.db.get_value("Employee", {"employee_name": employee_name, "company": company}, "name")
	if existing:
		return existing
	emp = frappe.get_doc(
		{
			"doctype": "Employee",
			"employee_name": employee_name,
			"first_name": employee_name,
			"company": company,
			"status": "Active",
			"date_of_joining": "2026-01-01",
			"gender": "Male",
		}
	)
	emp.flags.ignore_permissions = True
	emp.flags.ignore_mandatory = True
	emp.insert()
	return emp.name


def _make_customer(customer_name: str) -> str:
	"""Create a Customer if absent; return its name."""
	if frappe.db.exists("Customer", customer_name):
		return customer_name
	cust = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Company",
		}
	)
	cust.flags.ignore_permissions = True
	cust.flags.ignore_mandatory = True
	cust.insert()
	return cust.name
