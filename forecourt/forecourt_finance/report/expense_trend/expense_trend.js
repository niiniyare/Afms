frappe.query_reports["Expense Trend"] = {
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
		...forecourt.report_filters.period({ default: "Last 6 months" }),
		{
			fieldname: "expense_type",
			label: __("Expense Type"),
			fieldtype: "Link",
			options: "Expense Type",
		},
		{
			fieldname: "granularity",
			label: __("Granularity"),
			fieldtype: "Select",
			options: "Month\nWeek",
			default: "Month",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
