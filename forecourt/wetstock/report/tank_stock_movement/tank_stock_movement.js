frappe.query_reports["Tank Stock Movement"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.tank({ fieldname: "tank" }),
		forecourt.report_filters.product(),
		forecourt.report_filters.entry_type(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
