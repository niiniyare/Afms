from __future__ import annotations

from typing import ClassVar

import frappe
from frappe import _
from frappe.model.document import Document

from forecourt.errors import FMS_M602, FMSValidationError
from forecourt.setup.default_accounts import create_default_accounts


class ForecourtCompanySettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_overlapping_shifts: DF.Check
		approval_multiplier: DF.Float
		cash_over_account: DF.Link
		cash_short_account: DF.Link
		company: DF.Link
		credit_invoicing: DF.Literal["Per customer per shift", "Monthly"]
		cumulative_tolerance_pct: DF.Percent
		delivery_shortage_claims_account: DF.Link
		delivery_tolerance_pct: DF.Percent
		float_after_shift: DF.Literal["Stays in till", "Returned to safe"]
		fuel_stock_variance_account: DF.Link
		post_tank_variance: DF.Literal["Every shift with dips", "Last shift of day", "Outside tolerance only"]
		price_cross_check_amount: DF.Currency
		sales_posting_mode: DF.Literal["Shift summary", "Per transaction"]
		small_difference_amount: DF.Currency
		small_difference_pct: DF.Percent
		staff_shortage_receivable_account: DF.Link
		tank_tolerance_l: DF.Float
		tank_tolerance_pct: DF.Percent
		temperature_compensation: DF.Check
		voucher_clearing_account: DF.Link

	# end: auto-generated types

	# Maps fieldname → (required root_type, required account_type or None, forbidden account_type or None)
	_ACCOUNT_RULES: ClassVar[dict[str, tuple[str, str | None, str | None]]] = {
		"staff_shortage_receivable_account": ("Liability", "Payable", None),
		"cash_short_account": ("Expense", None, None),
		"cash_over_account": ("Income", None, None),
		"fuel_stock_variance_account": ("Expense", None, None),
		"delivery_shortage_claims_account": ("Asset", None, "Receivable"),
		"voucher_clearing_account": ("Asset", None, None),
	}

	def validate(self) -> None:
		self._validate_accounts()

	def _validate_accounts(self) -> None:
		errors: list[str] = []
		for fieldname, (root_type, req_acct_type, forbidden_acct_type) in self._ACCOUNT_RULES.items():
			account = self.get(fieldname)
			if not account:
				continue

			acct = frappe.db.get_value(
				"Account",
				account,
				["company", "root_type", "account_type"],
				as_dict=True,
			)
			if not acct:
				continue

			label = self.meta.get_label(fieldname)

			if acct.company != self.company:
				errors.append(
					_("[{0}] {1}: account {2} belongs to {3}, not {4}.").format(
						FMS_M602, label, account, acct.company, self.company
					)
				)
				continue

			if acct.root_type != root_type:
				errors.append(
					_("[{0}] {1}: account {2} must have root type {3} (got {4}).").format(
						FMS_M602, label, account, root_type, acct.root_type
					)
				)

			if req_acct_type and acct.account_type != req_acct_type:
				errors.append(
					_("[{0}] {1}: account {2} must have account type {3} (got {4}).").format(
						FMS_M602, label, account, req_acct_type, acct.account_type
					)
				)

			if forbidden_acct_type and acct.account_type == forbidden_acct_type:
				errors.append(
					_("[{0}] {1}: account {2} must not be of account type {3}.").format(
						FMS_M602, label, account, forbidden_acct_type
					)
				)

		if errors:
			raise FMSValidationError(FMS_M602, "<br>".join(errors))

	@frappe.whitelist()
	def create_default_accounts(self) -> None:
		"""Create the standard FMS accounts for this company and fill the mapping."""
		frappe.only_for(["System Manager", "Forecourt Administrator"])
		create_default_accounts(self)
		self.save()
