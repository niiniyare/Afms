frappe.query_reports["Exception Register"] = {
	filters: [...forecourt.report_filters.scope(), ...forecourt.report_filters.period()],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
