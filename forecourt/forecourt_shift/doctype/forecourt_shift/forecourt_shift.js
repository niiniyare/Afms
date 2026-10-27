// F16: Close button and background-close realtime handling.
frappe.ui.form.on("Forecourt Shift", {
	onload(frm) {
		// Register once; reload when background close finishes or fails.
		frappe.realtime.on("shift_closed", function (data) {
			if (data.shift !== frm.docname) return;
			frm.reload_doc();
			if (data.error) {
				frappe.msgprint({
					title: __("Close Failed"),
					message: __("Background close failed. See document comments for details."),
					indicator: "red",
				});
			}
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.status === "Reconciled") {
			frm.add_custom_button(__("Close"), function () {
				frappe.confirm(
					__("Close this shift and post all accounting entries?"),
					function () {
						frappe.call({
							method: "forecourt.forecourt_shift.close.close_shift",
							args: { shift_name: frm.docname },
							freeze: true,
							freeze_message: __("Closing shift…"),
							callback(r) {
								if (r.message === "submitted") {
									frm.reload_doc();
								} else if (r.message === "enqueued") {
									frm.reload_doc();
									frappe.show_alert(
										{
											message: __(
												"Large shift queued for background close. Status will update automatically."
											),
											indicator: "blue",
										},
										8
									);
								}
							},
						});
					}
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.docstatus === 0 && ["Open", "Reconciling"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("Import Transactions"),
				function () {
					_import_transactions_dialog(frm);
				},
				__("Tools")
			);
			frm.add_custom_button(
				__("Refresh Feeds"),
				function () {
					frm.call("refresh_feeds").then((r) => {
						if (r.message) {
							const n = r.message.created;
							frappe.show_alert({
								message: n
									? __("{0} feed transaction(s) added", [n])
									: __("No new feed transactions"),
								indicator: n ? "green" : "blue",
							});
							frm.reload_doc();
						}
					});
				},
				__("Tools")
			);
		}

		if (frm.doc.status === "Closing") {
			frm.disable_save();
			frm.set_intro(__("Closing in background…"), "blue");
		}
	},
});

function _import_transactions_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Import Transactions"),
		fields: [
			{
				fieldname: "provider",
				fieldtype: "Link",
				label: __("Payment Provider"),
				options: "Payment Provider",
				reqd: 1,
			},
			{
				fieldname: "file",
				fieldtype: "Attach",
				label: __("Statement File"),
				reqd: 1,
			},
		],
		primary_action_label: __("Import"),
		primary_action(values) {
			dialog.hide();
			frappe.show_alert({ message: __("Importing…"), indicator: "blue" });
			frappe.call({
				method: "forecourt.forecourt_integrations.statement_import.run_for_shift",
				args: {
					shift: frm.docname,
					provider: values.provider,
					file_url: values.file,
				},
				callback(r) {
					if (!r.exc && r.message) {
						const m = r.message;
						frappe.msgprint({
							title: __("Import Complete"),
							message: __(
								"Read: {0} · Created: {1} · Duplicate: {2} · Rejected: {3}",
								[m.rows_read, m.rows_created, m.rows_duplicate, m.rows_rejected]
							),
							indicator: m.rows_rejected ? "orange" : "green",
						});
						frm.reload_doc();
					}
				},
			});
		},
	});
	dialog.show();
}
