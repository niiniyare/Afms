frappe.query_reports["Clearing Account Ageing"] = {
	filters: [
		...forecourt.report_filters.scope(),
		forecourt.report_filters.as_of(),
		forecourt.report_filters.mode_of_payment(),
	],
};
