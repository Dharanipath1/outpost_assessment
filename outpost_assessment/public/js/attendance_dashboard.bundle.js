import { createApp } from "vue";
import AttendanceDashboardComponent from "../../outpost_assessment/page/attendance_dashboard/AttendanceDashboard.vue";

class AttendanceDashboard {
	constructor({ wrapper, page }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.init();
	}

	init() {
		this.page.set_title(__("Attendance Dashboard"));
		this.setup_app();
	}

	setup_app() {
		const app = createApp(AttendanceDashboardComponent);
		
		// Set global translation helper and other globals if available
		if (typeof SetVueGlobals !== "undefined") {
			SetVueGlobals(app);
		}
		
		// Mount the Vue application onto the page wrapper body
		this.$vue_app = app.mount(this.$wrapper.get(0));
	}
}

frappe.provide("frappe.ui");
frappe.ui.AttendanceDashboard = AttendanceDashboard;
export default AttendanceDashboard;
