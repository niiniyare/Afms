frappe.query_reports["Fleet Vehicle Consumption"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("company"),
			reqd: 1,
		},
		...forecourt.report_filters.scope_stations(),
		...forecourt.report_filters.period(),
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "vehicle",
			label: __("Vehicle"),
			fieldtype: "Link",
			options: "Customer Vehicle",
			get_query() {
				const customer = frappe.query_report.get_filter_value("customer");
				return customer ? { filters: { customer } } : {};
			},
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
