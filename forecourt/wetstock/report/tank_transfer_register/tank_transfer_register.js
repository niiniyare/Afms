frappe.query_reports["Tank Transfer Register"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last month" }),
		...forecourt.report_filters.tank(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
