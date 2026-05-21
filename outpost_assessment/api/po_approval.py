import frappe
import urllib.parse
from frappe.model.workflow import apply_workflow

@frappe.whitelist()
def approve(po_name, action):
    if frappe.session.user == "Guest":
        redirect_url = urllib.parse.quote(f"/api/method/outpost_assessment.api.po_approval.approve?po_name={po_name}&action={action}")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = f"/login?redirect-to={redirect_url}"
        return

    try:
        doc = frappe.get_doc("Purchase Order", po_name)
        apply_workflow(doc, action)
        frappe.db.commit()
        frappe.msgprint(f"Successfully applied '{action}' to Purchase Order {po_name}", alert=True)
    except Exception as e:
        frappe.msgprint(f"Could not approve {po_name}. Ensure you have the correct permissions. Error: {e}")
        
    # Redirect to the document so they can see the updated status
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"/app/purchase-order/{po_name}"
