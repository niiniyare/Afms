frappe.query_reports["Sales by Shift"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.shift_link(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
