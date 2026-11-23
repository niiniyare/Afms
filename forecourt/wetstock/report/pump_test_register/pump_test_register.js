frappe.query_reports["Pump Test Register"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 30 days" }),
		...forecourt.report_filters.nozzle(),
		...forecourt.report_filters.cashier(),
		{
			fieldname: "only_above_limit",
			label: __("Only Above Limit"),
			fieldtype: "Check",
			default: 0,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
