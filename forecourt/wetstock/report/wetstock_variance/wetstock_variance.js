frappe.query_reports["Wetstock Variance"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.tank({ fieldname: "tank" }),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
