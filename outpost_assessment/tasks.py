# Copyright (c) 2026, Dharanipathi and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import today
from frappe.utils.xlsxutils import make_xlsx

def retry_failed_webhooks():
    MAX_RETRIES = 3

    failed_logs = frappe.get_all(
        "Payment Webhook Log",
        filters={
            "status": "Failed",
            "retry_count": ["<", MAX_RETRIES],
        },
        fields=["name", "raw_payload", "retry_count"],
    )

    if not failed_logs:
        return

    for log in failed_logs:
        try:
            payload = json.loads(log.raw_payload or "{}")
            
            frappe.db.set_value(
                "Payment Webhook Log", 
                log.name, 
                {"retry_count": log.retry_count + 1, "status": "Pending"}, 
                update_modified=True
            )
            frappe.db.commit()

            frappe.enqueue(
                "outpost_assessment.api.payment.process_payment_webhook",
                queue="default",
                timeout=300,
                log_name=log.name,
                payload=payload,
            )
        except Exception as exc:
            frappe.db.rollback()
            frappe.logger().error(f"[Payment Retry] Failed to re-enqueue log {log.name}: {exc}")

def send_delayed_work_order_reminders():
    today_date = today()
    
    delayed_wos = frappe.get_all(
        "Work Order",
        filters={
            "status": ["in", ["Not Started", "In Process", "Stopped"]],
            "docstatus": 1,
            "expected_delivery_date": ["<", today_date]
        },
        fields=["name", "production_item", "qty", "expected_delivery_date", "company", "status"]
    )
    
    if not delayed_wos:
        frappe.logger().info("[Delayed WOs] No delayed Work Orders found today.")
        return
        
    managers = frappe.db.sql("""
        SELECT parent FROM `tabHas Role`
        WHERE role = 'Manufacturing Manager' AND parenttype = 'User'
        AND EXISTS (SELECT name FROM `tabUser` WHERE name = `tabHas Role`.parent AND enabled = 1)
    """, as_dict=True)
    
    if not managers:
        frappe.logger().info("[Delayed WOs] No active Manufacturing Managers found to email.")
        return
        
    recipients = [m.parent for m in managers]
    
    from frappe.utils.xlsxutils import make_xlsx

    html_rows = ""
    excel_data = [["Work Order", "Item", "Qty", "Expected Delivery", "Status"]]
    
    for wo in delayed_wos:
        html_rows += f"<tr><td>{wo.name}</td><td>{wo.production_item}</td><td>{wo.qty}</td><td>{wo.expected_delivery_date}</td><td>{wo.status}</td></tr>"
        excel_data.append([wo.name, wo.production_item, wo.qty, wo.expected_delivery_date, wo.status])
        
    message = f"""
    <h3>Delayed Work Orders Reminder</h3>
    <p>The following Work Orders have passed their expected delivery date and are still not completed:</p>
    <table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: left;'>
        <tr style='background-color: #f3f4f6;'>
            <th>Work Order</th>
            <th>Item</th>
            <th>Qty</th>
            <th>Expected Delivery</th>
            <th>Status</th>
        </tr>
        {html_rows}
    </table>
    <br>
    <p>Please review these orders immediately to prevent further delays.</p>
    """
    
    xlsx_file = make_xlsx(excel_data, "Delayed Work Orders")
    attachments = [{
        "fname": "Delayed_Work_Orders.xlsx",
        "fcontent": xlsx_file.getvalue()
    }]
    
    try:
        frappe.sendmail(
            recipients=recipients,
            subject="Action Required: Delayed Work Orders Reminder",
            message=message,
            attachments=attachments,
            now=True
        )
        frappe.logger().info(f"[Delayed WOs] Sent reminder email for {len(delayed_wos)} delayed orders to {len(recipients)} managers.")
    except Exception as e:
        frappe.logger().error(f"[Delayed WOs] Failed to send reminder email: {e}")

def notify_po_rejection(doc, method=None):
    if not doc.get_doc_before_save():
        return
        
    old_state = doc.get_doc_before_save().workflow_state
    new_state = doc.workflow_state
    
    if new_state == "Rejected" and old_state != "Rejected":
        comment = frappe.db.get_value("Comment", 
            {"reference_doctype": "Purchase Order", "reference_name": doc.name, "comment_type": "Workflow"}, 
            "content", order_by="creation desc")
            
        if not comment:
            comment = frappe.db.get_value("Comment", 
                {"reference_doctype": "Purchase Order", "reference_name": doc.name}, 
                "content", order_by="creation desc")
                
        reason = comment or "No reason provided."
        
        requestor_email = frappe.db.get_value("User", doc.owner, "email") or doc.owner
        
        frappe.sendmail(
            recipients=[requestor_email],
            subject=f"Purchase Order {doc.name} Rejected",
            message=f"<p>Your Purchase Order <b>{doc.name}</b> has been rejected.</p><p><b>Reason:</b> {reason}</p>",
            now=True
        )

def send_po_approval_reminders():
    pending_states = {
        "Pending HoD Approval": "Department Head",
        "Pending Finance Approval": "Finance Manager",
        "Pending CEO Approval": "CEO"
    }
    
    for state, role in pending_states.items():
        pos = frappe.get_all("Purchase Order", 
            filters={"workflow_state": state, "docstatus": 0},
            fields=["name", "supplier", "grand_total", "owner", "transaction_date"]
        )
        
        if not pos:
            continue
            
        users = frappe.db.sql("""
            SELECT parent FROM `tabHas Role`
            WHERE role = %s AND parenttype = 'User'
            AND EXISTS (SELECT name FROM `tabUser` WHERE name = `tabHas Role`.parent AND enabled = 1)
        """, (role,), as_dict=True)
        
        recipients = [u.parent for u in users]
        if not recipients:
            continue
            
        workflow_actions = frappe.db.sql("""
            SELECT action FROM `tabWorkflow Transition` 
            WHERE parent = 'Purchase order Approval' AND state = %s AND allowed = %s LIMIT 1
        """, (state, role), as_dict=True)
        action_name = workflow_actions[0].action if workflow_actions else "Approve"
        
        html_rows = ""
        for po in pos:
            doc_link = frappe.utils.get_url_to_form("Purchase Order", po.name)
            approve_link = frappe.utils.get_url() + f"/api/method/outpost_assessment.api.po_approval.approve?po_name={po.name}&action={action_name}"
            
            approve_btn = f"<a href='{approve_link}' style='background-color:#28a745;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-weight:bold;font-size:12px;display:inline-block;'>✓ {action_name}</a>"
            
            html_rows += f"<tr><td><a href='{doc_link}' style='font-weight:bold;'>{po.name}</a></td><td>{po.supplier}</td><td>₹ {po.grand_total}</td><td>{po.owner}</td><td style='text-align:center;'>{approve_btn}</td></tr>"
            
        message = f"""
        <h3>Pending Purchase Orders Approval</h3>
        <p>You have {len(pos)} Purchase Order(s) waiting for your approval as <b>{role}</b>:</p>
        <table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: left;'>
            <tr style='background-color: #f3f4f6;'>
                <th>PO Number</th>
                <th>Supplier</th>
                <th>Grand Total</th>
                <th>Requested By</th>
                <th style='text-align:center;'>Quick Action</th>
            </tr>
            {html_rows}
        </table>
        """
        
        try:
            frappe.sendmail(
                recipients=recipients,
                subject=f"Action Required: Pending PO Approvals ({role})",
                message=message
            )
            frappe.logger().info(f"[PO Reminders] Sent reminder for {len(pos)} POs to {role}.")
        except Exception as e:
            frappe.logger().error(f"[PO Reminders] Failed to send to {role}: {e}")
