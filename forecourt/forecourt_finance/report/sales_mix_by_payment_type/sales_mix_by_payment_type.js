frappe.query_reports["Sales Mix by Payment Type"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 30 days" }),
		{
			fieldname: "level",
			label: __("Level"),
			fieldtype: "Select",
			options: "Station\nCashier",
			default: "Station",
		},
		{
			fieldname: "flag_threshold_pct",
			label: __("Flag Threshold (points)"),
			fieldtype: "Float",
			default: 15,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "flag" && data && data.flag) {
			value = `<span style="color:orange;font-weight:bold">${value}</span>`;
		}
		return value;
	},
};
