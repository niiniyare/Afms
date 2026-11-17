frappe.query_reports["Payment Reconciliation"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.provider(),
		forecourt.report_filters.payment_status(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
