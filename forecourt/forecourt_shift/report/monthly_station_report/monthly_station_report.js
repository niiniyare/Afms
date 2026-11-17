frappe.query_reports["Monthly Station Report"] = {
	filters: [
		forecourt.report_filters.company(),
		forecourt.report_filters.station({ reqd: 1 }),
		...forecourt.report_filters.period(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
