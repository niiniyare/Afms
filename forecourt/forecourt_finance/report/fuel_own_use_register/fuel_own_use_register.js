frappe.query_reports["Fuel Own Use Register"] = {
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
		...forecourt.report_filters.product(),
		{
			fieldname: "purpose",
			label: __("Purpose"),
			fieldtype: "Link",
			options: "Own Use Purpose",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
