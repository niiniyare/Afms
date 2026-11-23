frappe.query_reports["Daily Station Report"] = {
	filters: [
		...forecourt.report_filters.scope(),
		forecourt.report_filters.as_of({ label: __("Date"), reqd: 1 }),
	],
};
