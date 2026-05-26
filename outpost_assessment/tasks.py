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
        
    HasRole = frappe.qb.DocType("Has Role")
    User = frappe.qb.DocType("User")
    recipients = (
        frappe.qb.from_(HasRole)
        .join(User).on(User.name == HasRole.parent)
        .select(HasRole.parent)
        .where(HasRole.role == "Manufacturing Manager")
        .where(HasRole.parenttype == "User")
        .where(User.enabled == 1)
        .run(pluck="parent")
    )

    if not recipients:
        frappe.logger().info("[Delayed WOs] No active Manufacturing Managers found to email.")
        return
        
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
        comment_info = frappe.db.get_value("Comment", 
            {"reference_doctype": "Purchase Order", "reference_name": doc.name, "comment_type": "Comment"}, 
            ["content", "comment_by"], as_dict=True, order_by="creation desc")
                
        reason = comment_info.content if comment_info else "No reason provided."
        rejected_by = comment_info.comment_by if comment_info else "System"
        
        requestor_email = frappe.db.get_value("User", doc.owner, "email") or doc.owner
        doc_link = frappe.utils.get_url_to_form("Purchase Order", doc.name)
        
        # Build beautiful item table
        from frappe.utils import fmt_money
        item_rows = ""
        for item in doc.items:
            item_rows += f"""
            <tr style="border-bottom: 1px solid #f3f4f6;">
                <td style="padding: 10px; font-size: 13px; color: #1f2937; font-family: sans-serif;"><b>{item.item_code}</b><br><span style="color: #6b7280; font-size: 11px;">{item.item_name or ''}</span></td>
                <td style="padding: 10px; font-size: 13px; text-align: right; color: #4b5563; font-family: sans-serif;">{item.qty} {item.uom}</td>
                <td style="padding: 10px; font-size: 13px; text-align: right; color: #4b5563; font-family: sans-serif;">{fmt_money(item.rate, currency=doc.currency)}</td>
                <td style="padding: 10px; font-size: 13px; text-align: right; font-weight: bold; color: #111827; font-family: sans-serif;">{fmt_money(item.amount, currency=doc.currency)}</td>
            </tr>
            """

        message = f"""
        <div style="background-color: #f9fafb; padding: 30px; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #f3f4f6;">
            <!-- Header -->
            <div style="border-bottom: 2px solid #fee2e2; padding-bottom: 15px; margin-bottom: 20px; text-align: center;">
                <span style="background-color: #fef2f2; color: #ef4444; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 9999px; display: inline-block; margin-bottom: 8px;">Workflow Alert</span>
                <h2 style="color: #991b1b; margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Purchase Order Rejected</h2>
                <p style="color: #4b5563; font-size: 14px; margin: 5px 0 0 0;">Document: <span style="font-weight: bold; color: #111827;">{doc.name}</span></p>
            </div>

            <!-- Rejection Card -->
            <div style="background-color: #fdf2f2; border-left: 4px solid #ef4444; padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 24px;">
                <p style="margin: 0 0 6px 0; font-size: 12px; font-weight: 600; text-transform: uppercase; color: #b91c1c; letter-spacing: 0.05em;">Rejection Reason (from {rejected_by})</p>
                <div style="font-size: 14px; color: #7f1d1d; line-height: 1.5; font-style: italic; font-weight: 500;">
                    "{reason}"
                </div>
            </div>

            <!-- PO Summary Card -->
            <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
                <h4 style="margin: 0 0 12px 0; font-size: 14px; color: #374151; font-weight: 600; border-bottom: 1px solid #f3f4f6; padding-bottom: 6px;">Order Details</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="font-size: 12px; color: #6b7280; padding: 4px 0;">Supplier:</td>
                        <td style="font-size: 12px; color: #111827; font-weight: bold; text-align: right; padding: 4px 0;">{doc.supplier}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 12px; color: #6b7280; padding: 4px 0;">Date:</td>
                        <td style="font-size: 12px; color: #111827; text-align: right; padding: 4px 0;">{doc.transaction_date}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 14px; color: #111827; font-weight: 600; padding: 8px 0 0 0; border-top: 1px solid #f3f4f6;">Grand Total:</td>
                        <td style="font-size: 16px; color: #b91c1c; font-weight: bold; text-align: right; padding: 8px 0 0 0; border-top: 1px solid #f3f4f6;">{fmt_money(doc.grand_total, currency=doc.currency)}</td>
                    </tr>
                </table>
            </div>

            <!-- Items Table -->
            <div style="margin-bottom: 24px;">
                <h4 style="margin: 0 0 10px 0; font-size: 13px; color: #4b5563; font-weight: 600;">Items List</h4>
                <div style="overflow-x: auto; background: white; border: 1px solid #e5e7eb; border-radius: 8px;">
                    <table style="width: 100%; border-collapse: collapse; min-width: 400px;">
                        <thead>
                            <tr style="background-color: #f9fafb; border-bottom: 1px solid #e5e7eb; text-align: left;">
                                <th style="padding: 10px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase;">Item</th>
                                <th style="padding: 10px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase; text-align: right;">Qty</th>
                                <th style="padding: 10px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase; text-align: right;">Rate</th>
                                <th style="padding: 10px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase; text-align: right;">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {item_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Call to Action -->
            <div style="text-align: center; margin-top: 28px;">
                <p style="font-size: 13px; color: #4b5563; margin-bottom: 15px;">Please review the comments, make the necessary corrections, and resubmit for approval.</p>
                <a href="{doc_link}" style="background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px; display: inline-block; box-shadow: 0 2px 4px rgba(220, 38, 38, 0.2);">
                    Edit Purchase Order
                </a>
            </div>
            
            <!-- Footer -->
            <div style="margin-top: 35px; border-top: 1px solid #e5e7eb; padding-top: 15px; text-align: center; font-size: 11px; color: #9ca3af;">
                This is an automated workflow notification from outpost_assessment. Please do not reply directly to this email.
            </div>
        </div>
        """
        
        frappe.sendmail(
            recipients=[requestor_email],
            subject=f"Purchase Order {doc.name} Rejected",
            message=message,
            now=True
        )

def send_po_approval_reminders():
    pending_states = {
        "Pending HoD Approval": "Department Head",
        "Pending Finance Approval": "Finance Manager",
        "Pending CEO Approval": "CEO"
    }
    
    for state, role in pending_states.items():
        pos_all = frappe.get_all("Purchase Order", 
            filters={"workflow_state": state, "docstatus": 0},
            fields=["name", "supplier", "grand_total", "owner", "transaction_date", "modified", "currency"]
        )
        
        from frappe.utils import now_datetime, fmt_money
        now = now_datetime()
        pos = [po for po in pos_all if (now - po.modified).total_seconds() >= 86400]
        
        if not pos:
            continue
            
        HasRole = frappe.qb.DocType("Has Role")
        User = frappe.qb.DocType("User")
        recipients = (
            frappe.qb.from_(HasRole)
            .join(User).on(User.name == HasRole.parent)
            .select(HasRole.parent)
            .where(HasRole.role == role)
            .where(HasRole.parenttype == "User")
            .where(User.enabled == 1)
            .run(pluck="parent")
        )

        if not recipients:
            continue
            
        html_rows = ""
        for po in pos:
            doc_link = frappe.utils.get_url_to_form("Purchase Order", po.name)
            approve_link = frappe.utils.get_url() + f"/api/method/outpost_assessment.api.po_approval.approve?po_name={po.name}&action=Approve"
            reject_link = frappe.utils.get_url() + f"/api/method/outpost_assessment.api.po_approval.approve?po_name={po.name}&action=Reject"
            
            approve_btn = f"<a href='{approve_link}' style='background-color: #10b981; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block; margin-right: 4px; box-shadow: 0 1px 2px rgba(16, 185, 129, 0.15);'>✓ Approve</a>"
            reject_btn = f"<a href='{reject_link}' style='background-color: #ef4444; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block; box-shadow: 0 1px 2px rgba(239, 68, 68, 0.15);'>✗ Reject</a>"
            
            html_rows += f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 12px; font-size: 13px; font-family: sans-serif;"><a href="{doc_link}" style="color: #4f46e5; font-weight: bold; text-decoration: none;">{po.name}</a></td>
                <td style="padding: 12px; font-size: 13px; color: #4b5563; font-family: sans-serif;">{po.supplier}</td>
                <td style="padding: 12px; font-size: 13px; font-weight: bold; color: #111827; font-family: sans-serif; text-align: right;">{fmt_money(po.grand_total, currency=po.currency)}</td>
                <td style="padding: 12px; font-size: 12px; color: #6b7280; font-family: sans-serif;">{po.owner}</td>
                <td style="padding: 12px; text-align: center; font-family: sans-serif; white-space: nowrap;">
                    {approve_btn}
                    {reject_btn}
                </td>
            </tr>
            """
            
        message = f"""
        <div style="background-color: #f9fafb; padding: 30px; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 750px; margin: 0 auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #f3f4f6;">
            <!-- Header -->
            <div style="border-bottom: 2px solid #e0e7ff; padding-bottom: 15px; margin-bottom: 20px; text-align: center;">
                <span style="background-color: #e0e7ff; color: #4f46e5; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 9999px; display: inline-block; margin-bottom: 8px;">Pending Review</span>
                <h2 style="color: #1e1b4b; margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Purchase Orders Pending Approval</h2>
                <p style="color: #4b5563; font-size: 14px; margin: 5px 0 0 0;">Role: <span style="font-weight: bold; color: #4f46e5;">{role}</span></p>
            </div>

            <p style="font-size: 14px; color: #4b5563; line-height: 1.6; margin-bottom: 20px;">
                Hello, you have <b>{len(pos)}</b> Purchase Order(s) that have been pending your approval for more than 24 hours. Please review or use the quick actions below to process them:
            </p>

            <!-- Table -->
            <div style="overflow-x: auto; background: white; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 20px;">
                <table style="width: 100%; border-collapse: collapse; min-width: 600px;">
                    <thead>
                        <tr style="background-color: #f9fafb; border-bottom: 1px solid #e5e7eb; text-align: left;">
                            <th style="padding: 12px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase;">PO Number</th>
                            <th style="padding: 12px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase;">Supplier</th>
                            <th style="padding: 12px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase; text-align: right;">Grand Total</th>
                            <th style="padding: 12px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase;">Requested By</th>
                            <th style="padding: 12px; font-size: 11px; font-weight: bold; color: #4b5563; font-family: sans-serif; text-transform: uppercase; text-align: center;">Quick Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {html_rows}
                    </tbody>
                </table>
            </div>

            <!-- Note -->
            <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px; border-radius: 0 6px 6px 0; font-size: 12px; color: #065f46; line-height: 1.5;">
                💡 <b>Quick Action Tip:</b> Clicking the quick action buttons in this email will securely execute the action and automatically open the document inside the Desk portal.
            </div>

            <!-- Footer -->
            <div style="margin-top: 35px; border-top: 1px solid #e5e7eb; padding-top: 15px; text-align: center; font-size: 11px; color: #9ca3af;">
                This is a scheduled automated reminder from outpost_assessment. Please do not reply directly to this email.
            </div>
        </div>
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
