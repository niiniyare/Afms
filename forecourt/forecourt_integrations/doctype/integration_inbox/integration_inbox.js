// Integration Inbox form — FMS-J03
frappe.ui.form.on("Integration Inbox", {
	refresh(frm) {
		if (frm.doc.status === "Failed" || frm.doc.status === "Received") {
			frm.add_custom_button(__("Retry"), function () {
				frappe.call({
					method: "forecourt.forecourt_integrations.inbox_processor.retry",
					args: { inbox_name: frm.docname },
					freeze: true,
					freeze_message: __("Re-queueing…"),
					callback() {
						frm.reload_doc();
						frappe.show_alert({ message: __("Retry enqueued"), indicator: "blue" });
					},
				});
			}).addClass("btn-warning");
		}
	},
});
