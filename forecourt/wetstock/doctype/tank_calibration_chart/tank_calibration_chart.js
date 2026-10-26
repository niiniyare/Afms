// Copyright (c) 2026, niiniyare and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tank Calibration Chart", {
	refresh: function (frm) {
		if (frm.doc.max_depth_mm) {
			frm.set_intro(
				__("Max depth: {0} mm | Max volume: {1} L", [
					frm.doc.max_depth_mm,
					frm.doc.max_volume_l,
				]),
				"blue"
			);
		}
	},
});
