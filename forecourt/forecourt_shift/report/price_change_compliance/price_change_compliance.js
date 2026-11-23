frappe.query_reports["Price Change Compliance"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last 30 days" }),
		{
			fieldname: "only_exceptions",
			label: __("Only Exceptions"),
			fieldtype: "Check",
			default: 1,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "flag" && data && data.flag) {
			value = `<span style="color:red;font-weight:bold">${value}</span>`;
		}
		return value;
	},
};
