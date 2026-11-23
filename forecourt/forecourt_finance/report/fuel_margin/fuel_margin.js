frappe.query_reports["Fuel Margin"] = {
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
		...forecourt.report_filters.period({ default: "Last month" }),
		{
			fieldname: "compare_with",
			label: __("Compare With"),
			fieldtype: "Select",
			options: "\nSame period last year\nPrior period",
		},
		...forecourt.report_filters.product(),
		{
			fieldname: "grouping",
			label: __("Group By"),
			fieldtype: "Select",
			options: "Station, then product\nProduct\nMonth",
			default: "Station, then product",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
