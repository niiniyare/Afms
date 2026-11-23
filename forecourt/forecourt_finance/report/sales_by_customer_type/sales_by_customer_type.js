frappe.query_reports["Sales by Customer Type"] = {
	filters: [
		...forecourt.report_filters.scope(),
		...forecourt.report_filters.period({ default: "Last month" }),
		{
			fieldname: "customer_group",
			label: __("Customer Group"),
			fieldtype: "Link",
			options: "Customer Group",
		},
		...forecourt.report_filters.product(),
		{
			fieldname: "grouping",
			label: __("Group By"),
			fieldtype: "Select",
			options: "Customer Type\nCustomer Group\nCustomer\nStation",
			default: "Customer Type",
		},
	],
	onload(report) {
		forecourt.report_filters.setup_period_handler(report);
	},
};
