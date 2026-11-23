frappe.query_reports["Station Comparison"] = {
	filters: [...forecourt.report_filters.scope(), ...forecourt.report_filters.period()],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
