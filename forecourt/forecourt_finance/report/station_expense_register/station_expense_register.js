frappe.query_reports["Station Expense Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("company"),
			reqd: 1,
		},
		...forecourt.report_filters.scope_stations(),
		...forecourt.report_filters.period(),
		{
			fieldname: "expense_type",
			label: __("Expense Type"),
			fieldtype: "Link",
			options: "Expense Type",
		},
		{
			fieldname: "cashier",
			label: __("Cashier"),
			fieldtype: "Link",
			options: "Employee",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
