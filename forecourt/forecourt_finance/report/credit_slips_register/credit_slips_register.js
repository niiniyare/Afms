frappe.query_reports["Credit Slips Register"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default_period: __("Month to Date") }),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
