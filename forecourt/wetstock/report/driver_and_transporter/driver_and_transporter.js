frappe.query_reports["Driver and Transporter"] = {
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
			fieldname: "transporter",
			label: __("Transporter"),
			fieldtype: "Link",
			options: "Supplier",
		},
		...forecourt.report_filters.product(),
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: "Transporter\nDriver\nSupplier",
			default: "Transporter",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
