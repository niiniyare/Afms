frappe.query_reports["Meter Movement"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("company"),
		},
		{
			fieldname: "station",
			label: __("Station"),
			fieldtype: "Link",
			options: "Station",
		},
		{
			fieldname: "dispenser",
			label: __("Dispenser"),
			fieldtype: "Link",
			options: "Pump",
		},
		{
			fieldname: "nozzle",
			label: __("Nozzle"),
			fieldtype: "Link",
			options: "Nozzle",
		},
		{
			fieldname: "item",
			label: __("Product"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.nowdate(), -30),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.nowdate(),
		},
	],
};
