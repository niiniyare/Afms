// Copyright (c) 2026, niiniyare and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fuel Tank", {
	refresh: function (frm) {
		if (frm.doc.capacity_l && !frm.doc.safe_fill_l && frm.is_new()) {
			frm.set_value("safe_fill_l", frm.doc.capacity_l * 0.95);
		}
	},
	capacity_l: function (frm) {
		if (frm.doc.capacity_l && !frm.doc.safe_fill_l) {
			frm.set_value("safe_fill_l", Math.round(frm.doc.capacity_l * 0.95));
		}
	},
});
