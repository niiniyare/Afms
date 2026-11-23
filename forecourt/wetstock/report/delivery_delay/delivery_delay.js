frappe.query_reports["Delivery Delay"] = {
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
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "only_late",
			label: __("Only Late"),
			fieldtype: "Check",
			default: 0,
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
