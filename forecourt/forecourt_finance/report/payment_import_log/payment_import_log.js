frappe.query_reports["Payment Import Log"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("company"),
			reqd: 1,
		},
		...forecourt.report_filters.period(),
		{
			fieldname: "provider",
			label: __("Provider"),
			fieldtype: "Link",
			options: "Payment Provider",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nComplete\nPartial\nFailed",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
