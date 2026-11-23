frappe.query_reports["Price History"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 90 days" }),
		...forecourt.report_filters.product(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
