frappe.query_reports["Water in Tanks"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 30 days" }),
		...forecourt.report_filters.tank(),
		{
			fieldname: "only_with_water",
			label: __("Only With Water"),
			fieldtype: "Check",
			default: 1,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
