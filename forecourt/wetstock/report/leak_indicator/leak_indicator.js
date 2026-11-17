frappe.query_reports["Leak Indicator"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		{
			fieldname: "tank",
			label: __("Tank"),
			fieldtype: "Link",
			options: "Fuel Tank",
			get_query: () => forecourt.report_filters.tank_query(),
		},
		{
			fieldname: "threshold_l",
			label: __("Flag Threshold (L)"),
			fieldtype: "Float",
			default: -20,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
