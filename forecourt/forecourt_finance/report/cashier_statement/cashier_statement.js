frappe.query_reports["Cashier Statement"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period(),
		{
			fieldname: "cashier",
			label: __("Cashier"),
			fieldtype: "Link",
			options: "Employee",
			reqd: 1,
			get_query() {
				return { filters: { fms_is_forecourt_cashier: 1 } };
			},
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
