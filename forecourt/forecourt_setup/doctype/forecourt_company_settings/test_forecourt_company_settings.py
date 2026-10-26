import frappe
from frappe.tests.utils import FrappeTestCase


def _company() -> str:
	return (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_all("Company", limit=1, pluck="name")[0]
	)


def _abbr(company: str) -> str:
	return frappe.get_cached_value("Company", company, "abbr")


def _account(name_bare: str, company: str) -> str:
	return f"{name_bare} - {_abbr(company)}"


def _get_account_props(account: str) -> dict:
	return frappe.db.get_value("Account", account, ["company", "root_type", "account_type"], as_dict=True)


class TestForecourtCompanySettings(FrappeTestCase):
	def setUp(self) -> None:
		self.company = _company()
		# Remove any leftover test record
		if frappe.db.exists("Forecourt Company Settings", self.company):
			frappe.delete_doc("Forecourt Company Settings", self.company, force=True)

	def tearDown(self) -> None:
		if frappe.db.exists("Forecourt Company Settings", self.company):
			frappe.delete_doc("Forecourt Company Settings", self.company, force=True)

	def _make_doc(self, **overrides) -> "frappe.Document":
		data = {
			"doctype": "Forecourt Company Settings",
			"company": self.company,
			"staff_shortage_receivable_account": _account("Creditors", self.company),
			"cash_short_account": _account("Indirect Expenses", self.company),
			"cash_over_account": _account("Indirect Income", self.company),
			"fuel_stock_variance_account": _account("Indirect Expenses", self.company),
			"delivery_shortage_claims_account": _account("Current Assets", self.company),
			"tank_tolerance_pct": 0.5,
			"tank_tolerance_l": 20,
			"approval_multiplier": 2,
		}
		data.update(overrides)
		return frappe.get_doc(data)

	# ------------------------------------------------------------------
	# Naming
	# ------------------------------------------------------------------

	def test_named_by_company(self) -> None:
		"""Record name equals company name."""
		doc = self._make_doc()
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.name, self.company)

	# ------------------------------------------------------------------
	# Account company validation
	# ------------------------------------------------------------------

	def test_account_wrong_company_refused(self) -> None:
		"""Account belonging to another company is refused (FMS-M602)."""
		other = frappe.get_all(
			"Company",
			filters=[["name", "!=", self.company]],
			limit=1,
			pluck="name",
		)
		if not other:
			self.skipTest("Only one company in the test site.")
		other_account = frappe.db.get_value(
			"Account",
			{"company": other[0], "root_type": "Expense", "is_group": 0},
			"name",
		)
		if not other_account:
			self.skipTest("No expense account found for other company.")
		doc = self._make_doc(cash_short_account=other_account)
		with self.assertRaisesRegex(frappe.ValidationError, r"FMS-M602"):
			doc.validate()

	# ------------------------------------------------------------------
	# Account type validation
	# ------------------------------------------------------------------

	def test_staff_shortage_must_be_payable(self) -> None:
		"""Staff Shortage Receivable must be account type Payable."""
		non_payable = frappe.db.get_value(
			"Account",
			{"company": self.company, "root_type": "Expense", "is_group": 0},
			"name",
		)
		if not non_payable:
			self.skipTest("No expense account found.")
		doc = self._make_doc(staff_shortage_receivable_account=non_payable)
		with self.assertRaisesRegex(frappe.ValidationError, r"FMS-M602"):
			doc.validate()

	def test_delivery_shortage_must_not_be_receivable(self) -> None:
		"""Delivery Shortage Claims account must not be of type Receivable."""
		receivable = frappe.db.get_value(
			"Account",
			{
				"company": self.company,
				"account_type": "Receivable",
				"is_group": 0,
			},
			"name",
		)
		if not receivable:
			self.skipTest("No receivable account found.")
		doc = self._make_doc(delivery_shortage_claims_account=receivable)
		with self.assertRaisesRegex(frappe.ValidationError, r"FMS-M602"):
			doc.validate()

	# ------------------------------------------------------------------
	# create_default_accounts
	# ------------------------------------------------------------------

	def test_create_default_accounts_idempotent(self) -> None:
		"""Calling create_default_accounts twice does not error."""
		doc = frappe.get_doc(
			{
				"doctype": "Forecourt Company Settings",
				"company": self.company,
			}
		)
		from forecourt.setup.default_accounts import create_default_accounts

		create_default_accounts(doc)
		create_default_accounts(doc)  # second call must not raise

	def test_create_default_accounts_fills_mapping(self) -> None:
		"""create_default_accounts fills at least the required account fields."""
		doc = frappe.get_doc(
			{
				"doctype": "Forecourt Company Settings",
				"company": self.company,
			}
		)
		from forecourt.setup.default_accounts import create_default_accounts

		create_default_accounts(doc)
		required = [
			"staff_shortage_receivable_account",
			"cash_short_account",
			"cash_over_account",
			"fuel_stock_variance_account",
			"delivery_shortage_claims_account",
		]
		for field in required:
			self.assertTrue(doc.get(field), f"{field} was not filled by create_default_accounts")

	def test_created_accounts_pass_validation(self) -> None:
		"""A settings doc built from create_default_accounts passes validate()."""
		doc = frappe.get_doc(
			{
				"doctype": "Forecourt Company Settings",
				"company": self.company,
			}
		)
		from forecourt.setup.default_accounts import create_default_accounts

		create_default_accounts(doc)
		doc.validate()  # must not raise
