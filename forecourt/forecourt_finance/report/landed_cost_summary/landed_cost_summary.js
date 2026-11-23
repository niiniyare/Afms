frappe.query_reports["Landed Cost Summary"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("company"),
			reqd: 1,
		},
		...forecourt.report_filters.period(),
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		...forecourt.report_filters.product(),
		{
			fieldname: "expense_account",
			label: __("Expense Account"),
			fieldtype: "Link",
			options: "Account",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
