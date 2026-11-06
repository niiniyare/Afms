"""Hide the six specialized FMS workspaces that were consolidated into the
single Forecourt workspace in task FMS-U02.

NOT registered in patches.txt — apply manually once the new Forecourt workspace
is confirmed by the owner:

    bench --site fms.localhost execute forecourt.patches.v0_2.retire_old_workspaces.execute
"""

import frappe

OLD_WORKSPACES = [
    "Shifts",
    "Wetstock",
    "Forecourt Finance",
    "Forecourt Operations",
    "Forecourt Group",
    "Forecourt Setup",
]


def execute() -> None:
    for name in OLD_WORKSPACES:
        if frappe.db.exists("Workspace", name):
            frappe.db.set_value("Workspace", name, "is_hidden", 1, update_modified=False)
    frappe.clear_cache()
