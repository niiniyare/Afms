frappe.query_reports["Sales Trend and Comparison"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 90 days" }),
		{
			fieldname: "granularity",
			label: __("Granularity"),
			fieldtype: "Select",
			options: "Week\nDay\nMonth",
			default: "Week",
		},
		{
			fieldname: "compare_with",
			label: __("Compare With"),
			fieldtype: "Select",
			options: "Same period last year\nPrior period\nNone",
			default: "Same period last year",
		},
		{
			fieldname: "measure",
			label: __("Measure"),
			fieldtype: "Select",
			options: "Litres\nAmount",
			default: "Litres",
		},
		...forecourt.report_filters.product(),
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
