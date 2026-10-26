// Copyright (c) 2026, niiniyare and contributors
// For license information, please see license.txt

frappe.ui.form.on("Forecourt Settings", {
	refresh(frm) {
		_check_basis_conflict(frm);
	},
	sales_basis(frm) {
		_check_basis_conflict(frm);
	},
	record_elec_cash(frm) {
		_check_basis_conflict(frm);
	},
	record_elec_meter(frm) {
		_check_basis_conflict(frm);
	},
	record_man_meter(frm) {
		_check_basis_conflict(frm);
	},
});

function _check_basis_conflict(frm) {
	const basis = frm.doc.sales_basis;
	const ecash = frm.doc.record_elec_cash;
	const emeter = frm.doc.record_elec_meter;
	const mmeter = frm.doc.record_man_meter;

	let msg = null;

	if (!ecash && !emeter && !mmeter) {
		msg = __("At least one meter (Elec Cash, Elec Meter or Man Meter) must be recorded.");
	} else if (basis === "Elec Cash" && !ecash) {
		msg = __("Sales basis Elec Cash requires Record Elec Cash to be enabled.");
	} else if (basis === "Elec Meter" && !emeter) {
		msg = __("Sales basis Elec Meter requires Record Elec Meter to be enabled.");
	} else if (basis === "Man Meter" && !mmeter) {
		msg = __("Sales basis Man Meter requires Record Man Meter to be enabled.");
	} else if (basis === "Highest" && !(ecash && emeter)) {
		msg = __("Sales basis Highest compares Elec Cash and Elec Meter. Both must be enabled.");
	}

	if (msg) {
		frm.dashboard.set_headline_alert(`<span class="indicator red">${msg}</span>`);
	} else {
		frm.dashboard.clear_headline();
	}
}
