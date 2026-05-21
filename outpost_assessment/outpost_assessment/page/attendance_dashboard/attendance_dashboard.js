// Copyright(c) 2026, Dharanipathi and contributors
// For license information, please see license.txt

frappe.pages["attendance-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Attendance Dashboard"),
		single_column: true,
	});
};

frappe.pages["attendance-dashboard"].on_page_show = function (wrapper) {
	load_attendance_dashboard(wrapper);
};

function load_attendance_dashboard(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	frappe.require("attendance_dashboard.bundle.js").then(() => {
		frappe.attendance_dashboard = new frappe.ui.AttendanceDashboard({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
