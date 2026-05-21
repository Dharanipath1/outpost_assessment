# Copyright (c) 2026, Dharanipathi and contributors
# For license information, please see license.txt

import os
import json
import frappe

@frappe.whitelist()
def get_attendance_data():
	app_path = frappe.get_app_path("outpost_assessment")
	mock_data_path = os.path.join(app_path, "outpost_assessment", "page", "attendance_dashboard", "mock_data.json")
	
	if os.path.exists(mock_data_path):
		try:
			with open(mock_data_path, "r", encoding="utf-8") as f:
				return json.load(f)
		except Exception as e:
			frappe.log_error(message=str(e), title="Error loading mock_data.json")
			return []
			
	return []
