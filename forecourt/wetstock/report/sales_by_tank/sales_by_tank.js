frappe.query_reports["Sales by Tank"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.tank({ fieldname: "tank" }),
		forecourt.report_filters.product(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
