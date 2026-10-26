// Copyright (c) 2026, niiniyare and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dispenser", {
	meters_override: function (frm) {
		if (!frm.doc.meters_override) {
			frm.set_value("record_elec_cash", 0);
			frm.set_value("record_elec_meter", 0);
			frm.set_value("record_man_meter", 0);
			frm.set_value("sales_basis", "");
		}
	},
});
