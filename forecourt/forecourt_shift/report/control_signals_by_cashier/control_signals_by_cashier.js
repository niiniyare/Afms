frappe.query_reports["Control Signals by Cashier"] = {
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
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
