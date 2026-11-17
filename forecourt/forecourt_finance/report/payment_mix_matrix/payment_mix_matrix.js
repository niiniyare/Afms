frappe.query_reports["Payment Mix Matrix"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.product(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
