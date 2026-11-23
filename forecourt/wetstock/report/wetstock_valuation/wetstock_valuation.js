frappe.query_reports["Wetstock Valuation"] = {
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
			fieldname: "as_at",
			label: __("As At"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(
				frappe.datetime.add_months(frappe.datetime.get_today(), -1)
			),
			reqd: 1,
		},
		...forecourt.report_filters.product(),
	],
};
