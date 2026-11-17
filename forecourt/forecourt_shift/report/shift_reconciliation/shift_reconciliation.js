frappe.query_reports["Shift Reconciliation"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.shift_link(),
		forecourt.report_filters.cashier(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
