frappe.query_reports["Sales by Pump and Nozzle"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.product(),
		forecourt.report_filters.dispenser(),
		forecourt.report_filters.nozzle(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
