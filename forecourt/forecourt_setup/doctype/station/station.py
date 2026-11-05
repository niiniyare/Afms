from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M601, FMS_M602, FMS_M603

_CODE_RE = re.compile(r"^[A-Z]{2}-[A-Z0-9]{2,5}-[A-Z0-9]{2,6}$")

_BASIS_TO_METER: dict[str, str] = {
	"Elec Cash": "record_elec_cash",
	"Elec Mtr": "record_elec_meter",
	"Man Mtr": "record_man_meter",
}


class Station(Document):
	def validate(self) -> None:
		self._validate_code()
		self._validate_accounts_and_warehouses()
		self._validate_meters()

	def after_insert(self) -> None:
		from forecourt.setup.walk_in_customer import create_walk_in_customer

		create_walk_in_customer(self)

	# ------------------------------------------------------------------
	# FMS-M601: station code pattern
	# ------------------------------------------------------------------

	def _validate_code(self) -> None:
		if not _CODE_RE.match(self.station_code or ""):
			frappe.throw(
				_(
					"{0}: Station code {1} does not match the required pattern"
					" CC-AREA-CODE (e.g. KE-NBO-WSTL)."
				).format(FMS_M601, frappe.bold(self.station_code)),
				frappe.ValidationError,
			)

	# ------------------------------------------------------------------
	# FMS-M602: linked accounts and warehouses must belong to company
	# ------------------------------------------------------------------

	def _validate_accounts_and_warehouses(self) -> None:
		company = self.company

		for fieldname in ("warehouse_group", "shop_warehouse"):
			value = self.get(fieldname)
			if not value:
				continue
			wh_company = frappe.db.get_value("Warehouse", value, "company")
			if wh_company and wh_company != company:
				frappe.throw(
					_("{0}: Warehouse {1} belongs to {2}, not {3}.").format(
						FMS_M602,
						frappe.bold(value),
						frappe.bold(wh_company),
						frappe.bold(company),
					),
					frappe.ValidationError,
				)

		for fieldname in ("safe_account", "cash_in_transit_account"):
			value = self.get(fieldname)
			if not value:
				continue
			acct_company = frappe.db.get_value("Account", value, "company")
			if acct_company and acct_company != company:
				frappe.throw(
					_("{0}: Account {1} belongs to {2}, not {3}.").format(
						FMS_M602,
						frappe.bold(value),
						frappe.bold(acct_company),
						frappe.bold(company),
					),
					frappe.ValidationError,
				)

		if self.cost_center:
			cc_company = frappe.db.get_value("Cost Center", self.cost_center, "company")
			if cc_company and cc_company != company:
				frappe.throw(
					_("{0}: Cost Center {1} belongs to {2}, not {3}.").format(
						FMS_M602,
						frappe.bold(self.cost_center),
						frappe.bold(cc_company),
						frappe.bold(company),
					),
					frappe.ValidationError,
				)

		for row in self.till_accounts or []:
			if not row.account:
				continue
			acct_company = frappe.db.get_value("Account", row.account, "company")
			if acct_company and acct_company != company:
				frappe.throw(
					_("{0}: Till account {1} (row {2}) belongs to {3}, not {4}.").format(
						FMS_M602,
						frappe.bold(row.account),
						row.idx,
						frappe.bold(acct_company),
						frappe.bold(company),
					),
					frappe.ValidationError,
				)

	# ------------------------------------------------------------------
	# FMS-M603: sales basis consistent with recorded meters
	# ------------------------------------------------------------------

	def _validate_meters(self) -> None:
		if self.use_settings_meters:
			return
		sales_basis = self.sales_basis
		if not sales_basis:
			return

		if sales_basis == "Highest":
			recorded = sum(
				[
					int(bool(self.record_elec_cash)),
					int(bool(self.record_elec_meter)),
					int(bool(self.record_man_meter)),
				]
			)
			if recorded < 2:
				frappe.throw(
					_("{0}: Sales basis {1} requires at least two meters to be recorded.").format(
						FMS_M603, frappe.bold(sales_basis)
					),
					frappe.ValidationError,
				)
		else:
			required_field = _BASIS_TO_METER.get(sales_basis)
			if required_field and not self.get(required_field):
				frappe.throw(
					_("{0}: Sales basis {1} requires the corresponding meter to be recorded.").format(
						FMS_M603, frappe.bold(sales_basis)
					),
					frappe.ValidationError,
				)
