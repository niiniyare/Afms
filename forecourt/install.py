import frappe


def after_install() -> None:
	ensure_desktop_icon()


def after_migrate() -> None:
	ensure_desktop_icon()


def ensure_desktop_icon() -> None:
	screen = frappe.get_hooks("add_to_apps_screen", app_name="forecourt")
	if not screen:
		return

	entry = screen[0]
	label = entry.get("title")
	if frappe.db.exists("Desktop Icon", label):
		return

	icon = frappe.new_doc("Desktop Icon")
	icon.label = label
	icon.link_type = "External"
	icon.icon_type = "App"
	icon.app = "forecourt"
	icon.link = entry.get("route")
	icon.logo_url = entry.get("logo")
	icon.insert(ignore_permissions=True, ignore_if_duplicate=True)

	from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

	clear_desktop_icons_cache()
