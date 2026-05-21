import frappe
from frappe import _
import erpnext.manufacturing.doctype.work_order.work_order_dashboard as standard_dashboard

def get_data(data=None):
    if not data:
        data = standard_dashboard.get_data()
    
    found = False
    for group in data.get("transactions", []):
        if "Stock Reservation Entry" in group.get("items", []):
            found = True
            break
            
    if not found:
        added = False
        for group in data.get("transactions", []):
            if group.get("label") == _("Stock") or group.get("label") == "Stock":
                group.setdefault("items", []).append("Stock Reservation Entry")
                added = True
                break
                
        if not added:
            data.setdefault("transactions", []).append({
                "label": _("Stock"),
                "items": ["Stock Reservation Entry"]
            })
            
    if "non_standard_fieldnames" not in data:
        data["non_standard_fieldnames"] = {}
    data["non_standard_fieldnames"]["Stock Reservation Entry"] = "voucher_no"
            
    return data
