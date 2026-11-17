frappe.query_reports["Delivery Variance"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.tank({ fieldname: "tank" }),
		forecourt.report_filters.supplier(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
