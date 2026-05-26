app_name = "outpost_assessment"
app_title = "Outpost Assessment"
app_publisher = "Dharanipathi"
app_description = "Assessment for Outpost"
app_email = "dharanipathi.off@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "outpost_assessment",
# 		"logo": "/assets/outpost_assessment/logo.png",
# 		"title": "Outpost Assessment",
# 		"route": "/outpost_assessment",
# 		"has_permission": "outpost_assessment.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/outpost_assessment/css/outpost_assessment.css"
# app_include_js = "/assets/outpost_assessment/js/outpost_assessment.js"

# include js, css files in header of web template
# web_include_css = "/assets/outpost_assessment/css/outpost_assessment.css"
# web_include_js = "/assets/outpost_assessment/js/outpost_assessment.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "outpost_assessment/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Work Order": "outpost_assessment/client_scripts/work_order.js",
	"Purchase Order": "outpost_assessment/client_scripts/purchase_order.js"
}
doctype_list_js = {
	"Production Request": "outpost_assessment/doctype/production_request/production_request_list.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "outpost_assessment/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "outpost_assessment.utils.jinja_methods",
# 	"filters": "outpost_assessment.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "outpost_assessment.install.before_install"
after_install = "outpost_assessment.outpost_assessment.setup.create_custom_fields"
after_migrate = "outpost_assessment.outpost_assessment.setup.create_custom_fields"

# Uninstallation
# ------------

# before_uninstall = "outpost_assessment.uninstall.before_uninstall"
# after_uninstall = "outpost_assessment.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "outpost_assessment.utils.before_app_install"
# after_app_install = "outpost_assessment.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "outpost_assessment.utils.before_app_uninstall"
# after_app_uninstall = "outpost_assessment.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "outpost_assessment.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Work Order": {
		"on_update": "outpost_assessment.outpost_assessment.doctype.production_request.production_request.update_production_request_status"
	},
	"Stock Entry": {
		"before_insert": "outpost_assessment.outpost_assessment.overrides.stock_reservation.map_reservations_to_stock_entry",
		"before_submit": "outpost_assessment.outpost_assessment.overrides.stock_reservation.consume_reservation_on_stock_entry",
		"on_submit": "outpost_assessment.outpost_assessment.doctype.production_request.production_request.update_pr_status_from_stock_entry",
		"on_cancel": [
            "outpost_assessment.outpost_assessment.overrides.stock_reservation.restore_reservation_on_stock_entry_cancel",
            "outpost_assessment.outpost_assessment.doctype.production_request.production_request.update_pr_status_from_stock_entry"
        ]
	},
    "Purchase Order": {
        "validate": "outpost_assessment.api.po_approval.enforce_rejection_comment",
        "on_update": "outpost_assessment.tasks.notify_po_rejection"
    }
}


# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"outpost_assessment.tasks.all"
# 	],
# 	"daily": [
# 		"outpost_assessment.tasks.daily"
# 	],
# 	"hourly": [
# 		"outpost_assessment.tasks.hourly"
# 	],
# 	"weekly": [
# 		"outpost_assessment.tasks.weekly"
# 	],
# 	"monthly": [
# 		"outpost_assessment.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "outpost_assessment.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "outpost_assessment.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
    "Work Order": ("outpost_assessment.outpost_assessment.overrides.work_order.get_data"),
    "Stock Entry": ("outpost_assessment.outpost_assessment.overrides.stock_entry.get_data"),
}
# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

ignore_links_on_delete = ["Payment Webhook Log"]

# Request Events
# ----------------
# before_request = ["outpost_assessment.utils.before_request"]
# after_request = ["outpost_assessment.utils.after_request"]

# Job Events
# ----------
# before_job = ["outpost_assessment.utils.before_job"]
# after_job = ["outpost_assessment.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"outpost_assessment.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

scheduler_events = {
	"hourly": [
		"outpost_assessment.tasks.retry_failed_webhooks"
	],
	"daily": [
		"outpost_assessment.tasks.send_delayed_work_order_reminders",
		"outpost_assessment.tasks.send_po_approval_reminders"
	]
}

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Outpost Assessment"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Outpost Assessment"]]},
    {"dt": "Workflow", "filters": [["name", "=", "Purchase order Approval"]]},
    {"dt": "Workflow State", "filters": [["workflow_state_name", "in", ["Draft", "Pending HoD Approval", "Pending Finance Approval", "Pending CEO Approval", "Approved", "Rejected", "Cancelled"]]]},
    {"dt": "Workflow Action Master", "filters": [["workflow_action_name", "in", ["Approve", "Reject", "Submit for Approval", "Resubmit", "Cancel"]]]}
]

