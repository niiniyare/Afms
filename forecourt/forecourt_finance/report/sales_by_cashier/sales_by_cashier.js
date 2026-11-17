frappe.query_reports["Sales by Cashier"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.cashier(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
