frappe.query_reports["Equipment Register"] = {
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
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nActive\nOut of service\nDecommissioned",
		},
		...forecourt.report_filters.product(),
	],
};
