// Copyright (c) 2026, niiniyare and contributors
// For license information, please see license.txt

frappe.ui.form.on("Nozzle", {
	refresh: function (frm) {
		if (frm.doc.station) {
			frm.set_query("tank", function () {
				return { filters: { station: frm.doc.station } };
			});
		}
	},
	dispenser: function (frm) {
		if (frm.doc.station) {
			frm.set_query("tank", function () {
				return { filters: { station: frm.doc.station } };
			});
		}
	},
});
