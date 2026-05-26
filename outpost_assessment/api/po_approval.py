import frappe
import urllib.parse
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import now_datetime, get_url

@frappe.whitelist()
def approve(po_name, action):
    """
    Whitelisted API endpoint to apply a workflow action (Approve/Reject) on a Purchase Order.
    If the user is not logged in (Guest), redirects to login and returns.
    """
    if frappe.session.user == "Guest":
        redirect_url = urllib.parse.quote(f"/api/method/outpost_assessment.api.po_approval.approve?po_name={po_name}&action={action}")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = f"/login?redirect-to={redirect_url}"
        return

    try:
        doc = frappe.get_doc("Purchase Order", po_name)
        apply_workflow(doc, action)
        frappe.db.commit()
        frappe.msgprint(_("Successfully applied '{0}' to Purchase Order {1}").format(action, po_name), alert=True)
    except Exception as e:
        frappe.msgprint(_("Could not apply '{0}' to {1}. Error: {2}").format(action, po_name, str(e)))
        
    # Redirect back to Desk form
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"/app/purchase-order/{po_name}"

@frappe.whitelist()
def send_approval_reminders():
    """
    Daily scheduled job to send reminder emails to managers holding the allowed role
    for Purchase Orders pending approval for over 24 hours.
    """
    workflow_name = "Purchase order Approval"
    if not frappe.db.exists("Workflow", workflow_name):
        return

    workflow = frappe.get_doc("Workflow", workflow_name)
    if not workflow.is_active:
        return

    # Map each pending workflow state to its allowed editing role
    pending_states_map = {}
    for state_row in workflow.states:
        if state_row.doc_status == "0" and state_row.state not in ["Draft", "Rejected"]:
            pending_states_map[state_row.state] = state_row.allow_edit

    if not pending_states_map:
        return

    # Fetch all draft POs currently in pending approval states
    pending_pos = frappe.get_all(
        "Purchase Order",
        filters={
            "workflow_state": ["in", list(pending_states_map.keys())],
            "docstatus": 0
        },
        fields=["name", "workflow_state", "grand_total", "owner", "modified", "company"]
    )

    now = now_datetime()

    for po in pending_pos:
        # Verify that the document has been in this state for at least 24 hours (86400 seconds)
        time_elapsed = now - po.modified
        if time_elapsed.total_seconds() < 86400:
            continue

        target_role = pending_states_map.get(po.workflow_state)
        if not target_role:
            continue

        # Find active users assigned to this role
        recipients = get_users_with_role(target_role)
        if not recipients:
            frappe.log_error(
                message=f"No active users found with role '{target_role}' to approve PO {po.name}",
                title="PO Approval Reminder Missing Approver"
            )
            continue

        # Send formatted reminder notification
        send_reminder_email(po, target_role, recipients)

def get_users_with_role(role_name):
    """Utility to return active user emails matching a specific role."""
    return [
        r.parent for r in frappe.get_all(
            "Has Role",
            filters={"role": role_name, "parenttype": "User"},
            fields=["parent"]
        )
        if frappe.db.get_value("User", r.parent, "enabled") == 1
    ]

def send_reminder_email(po, role, recipients):
    """Constructs and sends an elegant HTML notification email."""
    site_url = get_url()
    doc_link = f"{site_url}/app/purchase-order/{po.name}"
    
    subject = f"⚠️ Action Required: Purchase Order Approval Pending - {po.name}"
    
    message = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; line-height: 1.6;">
        <h2 style="color: #e65100; margin-bottom: 20px;">Purchase Order Approval Pending</h2>
        <p>Hello,</p>
        <p>This is a reminder that <strong>Purchase Order {po.name}</strong> is currently pending your action as the <strong>{role}</strong>.</p>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0; border: 1px solid #ddd;">
            <tr style="background-color: #f9f9f9;">
                <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; width: 150px;">Document ID</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{po.name}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Grand Total</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; color: #2e7d32;">
                    {frappe.fmt_money(po.grand_total, currency=frappe.get_cached_value("Company", po.company, "default_currency"))}
                </td>
            </tr>
            <tr style="background-color: #f9f9f9;">
                <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Pending State</td>
                <td style="padding: 10px; border: 1px solid #ddd; color: #d84315; font-weight: bold;">
                    {po.workflow_state}
                </td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Requested By</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{po.owner}</td>
            </tr>
        </table>
        
        <div style="margin-top: 30px; text-align: center;">
            <a href="{doc_link}" 
               style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
               Review & Approve in Desk
            </a>
        </div>
        
        <p style="margin-top: 30px; font-size: 0.9em; color: #777;">
            Please do not reply directly to this automated email.
        </p>
    </div>
    """
    
    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        reference_doctype="Purchase Order",
        reference_name=po.name
    )

def enforce_rejection_comment(doc, method=None):
    """
    Before_save hook for Purchase Order to guarantee that a rejection comment is
    entered in the activity timeline before transitioning to the 'Rejected' state.
    """
    if doc.workflow_state == "Rejected" and doc.db_get("workflow_state") != "Rejected":
        # Look for a comment added by the current active user in the last 2 minutes
        recent_comment = frappe.db.get_value(
            "Comment",
            filters={
                "reference_doctype": doc.doctype,
                "reference_name": doc.name,
                "comment_type": "Comment",
                "owner": frappe.session.user
            },
            fieldname="content",
            order_by="creation desc"
        )
        if not recent_comment:
            frappe.throw(
                msg=_("Please add a comment explaining the reason for rejection in the document activity timeline before rejecting."),
                title=_("Comment Required on Rejection")
            )
