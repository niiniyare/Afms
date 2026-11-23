frappe.query_reports["Shortage Recovery"] = {
	filters: [
		forecourt.report_filters.company(),
		forecourt.report_filters.station(),
		forecourt.report_filters.cashier(),
		forecourt.report_filters.as_of({
			fieldname: "as_at",
			label: __("As At"),
			default: frappe.datetime.get_today(),
		}),
		{
			fieldname: "only_outstanding",
			label: __("Only Outstanding"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
