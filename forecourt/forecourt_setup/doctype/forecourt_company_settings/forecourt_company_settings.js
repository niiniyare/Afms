// Browsers autofill saved logins into the fiscal credential fields. Stop that, and
// never save credentials the user did not type.
const FISCAL_FIELDS = [
	"fiscal_device_id",
	"fiscal_device_serial",
	"fiscal_api_url",
	"fiscal_api_key",
];

function _block_autofill(frm) {
	FISCAL_FIELDS.forEach((fieldname) => {
		const field = frm.fields_dict[fieldname];
		if (!field || !field.$input) return;
		field.$input.attr({
			autocomplete: "new-password",
			"data-lpignore": "true",
			"data-1p-ignore": "true",
		});
	});
}

frappe.ui.form.on("Forecourt Company Settings", {
	refresh(frm) {
		_block_autofill(frm);
		$(".frappe-control[data-fieldname^='fiscal_'] input").removeAttr("data-user-edited");
		// Chrome fills after render; re-apply the attributes once it has.
		frm.__fiscal_loaded = FISCAL_FIELDS.reduce(
			(acc, f) => ({ ...acc, [f]: frm.doc[f] || "" }),
			{}
		);
		setTimeout(() => _block_autofill(frm), 300);

		if (!frm.is_new()) {
			frm.add_custom_button(__("Create Default Accounts"), function () {
				frappe.call({
					method: "forecourt.forecourt_setup.doctype.forecourt_company_settings.forecourt_company_settings.create_default_accounts",
					args: { company: frm.doc.company },
					freeze: true,
					callback(r) {
						if (!r.message) return;
						const rep = r.message;
						const lines = [rep.summary];
						(rep.clearing || []).forEach((c) => {
							lines.push(`${c.mode_of_payment}: ${c.account} (${c.status})`);
						});
						frappe.msgprint({
							title: __("Default Accounts"),
							message: lines.map((l) => frappe.utils.escape_html(l)).join("<br>"),
							indicator: "green",
						});
						frm.reload_doc();
					},
				});
			});
		}
	},

	validate(frm) {
		// Refuse credentials that appeared without the user typing them (browser autofill).
		const loaded = frm.__fiscal_loaded || {};
		const autofilled = FISCAL_FIELDS.filter((f) => {
			if (!frm.doc[f] || frm.doc[f] === loaded[f]) return false;
			const field = frm.fields_dict[f];
			return field && field.$input && field.$input.attr("data-user-edited") !== "1";
		});
		if (autofilled.length) {
			autofilled.forEach((f) => frm.set_value(f, loaded[f] || ""));
			frappe.throw(
				__(
					"Browser autofill was removed from the fiscal fields. Type credentials in manually, then save."
				)
			);
		}
	},
});

// Autofill never fires key events; only real typing or pasting marks a field as user-edited.
$(document).on("keydown paste", ".frappe-control[data-fieldname^='fiscal_'] input", function () {
	$(this).attr("data-user-edited", "1");
});
