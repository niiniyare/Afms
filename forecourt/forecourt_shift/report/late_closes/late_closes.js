frappe.query_reports["Late Closes"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		{
			fieldname: "late_hours",
			label: __("Late Threshold (hours)"),
			fieldtype: "Float",
			default: 12,
		},
		{
			fieldname: "late_only",
			label: __("Only Late"),
			fieldtype: "Check",
			default: 0,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
