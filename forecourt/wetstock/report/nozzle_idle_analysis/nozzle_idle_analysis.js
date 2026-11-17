frappe.query_reports["Nozzle Idle Analysis"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		{
			fieldname: "min_idle_days",
			label: __("Min Idle Days"),
			fieldtype: "Int",
			default: 0,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
