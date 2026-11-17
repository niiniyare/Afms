frappe.query_reports["Cash Count by Currency"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		forecourt.report_filters.cashier(),
		{
			fieldname: "currency",
			label: __("Currency"),
			fieldtype: "Link",
			options: "Currency",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
