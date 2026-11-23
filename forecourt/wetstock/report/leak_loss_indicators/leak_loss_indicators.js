frappe.query_reports["Leak and Loss Indicators"] = {
	filters: [
		...forecourt.report_filters.scope(),
		{
			fieldname: "window_days",
			label: __("Window (days)"),
			fieldtype: "Int",
			default: 30,
		},
		...forecourt.report_filters.product(),
		{
			fieldname: "min_consecutive_loss_shifts",
			label: __("Consecutive Loss Shifts Threshold"),
			fieldtype: "Int",
			default: 5,
		},
	],
};
