frappe.provide("forecourt");

/**
 * If a new document has a top-level `station` field and it is blank,
 * pre-fill it from the current user's Employee.fms_default_station (stored
 * in frappe.boot by forecourt.boot.get_bootinfo).  The user may override it.
 */
forecourt.apply_station_default = function (frm) {
	if (!frm.is_new()) return;
	if (frm.doc.station) return;
	if (!frm.fields_dict.station) return;

	const station = frappe.boot.fms_user_station;
	if (station) {
		frm.set_value("station", station);
	}
};

// Doctypes that receive a top-level station field from the Accounting Dimension
[
	"Sales Invoice",
	"Purchase Invoice",
	"Payment Entry",
	"Purchase Receipt",
	"Sales Order",
	"Purchase Order",
	"Stock Entry",
	"Delivery Note",
].forEach(function (doctype) {
	frappe.ui.form.on(doctype, {
		onload: function (frm) {
			forecourt.apply_station_default(frm);
		},
	});
});
