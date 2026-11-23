frappe.query_reports["Segregation of Duties"] = {
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
			fieldname: "only_violations",
			label: __("Only Violations"),
			fieldtype: "Check",
			default: 0,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
