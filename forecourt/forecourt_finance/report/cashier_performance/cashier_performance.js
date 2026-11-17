frappe.query_reports["Cashier Performance"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.cashier(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
