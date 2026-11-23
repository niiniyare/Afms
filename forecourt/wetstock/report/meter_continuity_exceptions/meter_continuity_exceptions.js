frappe.query_reports["Meter Continuity Exceptions"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 30 days" }),
		{
			fieldname: "exception_type",
			label: __("Type"),
			fieldtype: "Select",
			options: "\nGap\nRollover\nMeter Change\nManual Adjustment\nCorrection",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "flag" && data && data.flag === "Unexplained") {
			value = `<span style="color:red;font-weight:bold">${value}</span>`;
		}
		return value;
	},
};
