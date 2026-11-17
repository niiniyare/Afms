frappe.query_reports["Sales by Product"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.product(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
