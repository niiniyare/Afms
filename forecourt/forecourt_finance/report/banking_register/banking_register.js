frappe.query_reports["Banking Register"] = {
	filters: [
		forecourt.report_filters.company(),
		forecourt.report_filters.station(),
		...forecourt.report_filters.period(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
