# Copyright (c) 2026, Dharanipathi and contributors
# For license information, please see license.txt

import hashlib
import hmac
import json
import traceback
import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def update_status():
    settings = frappe.get_single("Payment Gateway Settings")

    if not settings.is_enabled:
        frappe.throw(_("Payment gateway integration is currently disabled."), frappe.PermissionError)

    raw_body = frappe.request.get_data()
    incoming_signature = frappe.get_request_header("X-Signature", "")

    if not incoming_signature:
        frappe.throw(_("Missing X-Signature header."), frappe.AuthenticationError)

    secret_bytes = settings.get_password("webhook_secret").encode("utf-8")
    expected_mac = hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()
    expected_signature = f"hmac-sha256={expected_mac}"

    if not hmac.compare_digest(expected_signature, incoming_signature):
        frappe.local.response["http_status_code"] = 401
        return {"status": "error", "message": _("Invalid signature.")}

    try:
        payload = json.loads(raw_body)
    except (ValueError, TypeError):
        frappe.throw(_("Request body must be valid JSON."), frappe.ValidationError)

    transaction_id = payload.get("transaction_id")
    if not transaction_id:
        frappe.throw(_("Payload must contain 'transaction_id'."), frappe.ValidationError)

    if frappe.db.exists("Payment Webhook Log", {"transaction_id": transaction_id}):
        return {"status": "duplicate", "message": _("Transaction already processed.")}

    log = frappe.get_doc({
        "doctype": "Payment Webhook Log",
        "transaction_id": transaction_id,
        "status": "Pending",
        "amount": payload.get("amount"),
        "currency": payload.get("currency", "INR"),
        "invoice_id": payload.get("invoice_id"),
        "raw_payload": json.dumps(payload, indent=2),
        "retry_count": 0,
    })
    log.insert(ignore_permissions=True)
    frappe.db.commit()

    frappe.enqueue(
        "outpost_assessment.api.payment.process_payment_webhook",
        queue="default",
        timeout=300,
        log_name=log.name,
        payload=payload,
    )

    return {"status": "queued", "log": log.name}

def process_payment_webhook(log_name, payload):
    log = frappe.get_doc("Payment Webhook Log", log_name)
    log.status = "Processing"
    log.save(ignore_permissions=True)
    frappe.db.commit()

    original_user = frappe.session.user if (frappe.session and hasattr(frappe.session, "user")) else None
    frappe.set_user("Administrator")

    try:
        if payload.get("status") != "success":
            frappe.get_doc("Payment Webhook Log", log_name).db_set({
                "status": "Failed",
                "error_message": _("Gateway reported payment as non-successful: {0}").format(payload.get("status", "unknown"))
            })
            return

        invoice_id = payload.get("invoice_id")
        if not invoice_id:
            frappe.throw(_("Payload is missing 'invoice_id'."))

        invoice = frappe.get_doc("Sales Invoice", invoice_id)

        if invoice.outstanding_amount <= 0:
            frappe.get_doc("Payment Webhook Log", log_name).db_set({
                "status": "Failed",
                "error_message": _("Invoice {0} has no outstanding balance.").format(invoice_id)
            })
            return

        amount = float(payload.get("amount", 0))
        if amount <= 0:
            frappe.throw(_("Payment amount must be greater than zero."))

        company = invoice.company
        receivable_account = frappe.db.get_value("Company", company, "default_receivable_account")
        cash_account = frappe.db.get_value("Company", company, "default_cash_account") or frappe.db.get_value(
            "Account",
            {"company": company, "account_type": "Cash", "is_group": 0},
            "name",
        )

        if not receivable_account or not cash_account:
            frappe.throw(
                _("Company {0} is missing default receivable or cash account.").format(company)
            )

        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": frappe.utils.today(),
            "company": company,
            "mode_of_payment": "Cash",
            "party_type": "Customer",
            "party": invoice.customer,
            "paid_from": receivable_account,
            "paid_to": cash_account,
            "paid_from_account_currency": invoice.currency,
            "paid_to_account_currency": invoice.currency,
            "paid_amount": amount,
            "received_amount": amount,
            "reference_no": payload.get("transaction_id"),
            "reference_date": frappe.utils.today(),
            "remarks": _("Auto-created from webhook. Transaction ID: {0}").format(payload.get("transaction_id")),
            "references": [
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": invoice_id,
                    "total_amount": invoice.grand_total,
                    "outstanding_amount": invoice.outstanding_amount,
                    "allocated_amount": min(amount, invoice.outstanding_amount),
                }
            ],
        })
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()

        log_doc = frappe.get_doc("Payment Webhook Log", log_name)
        log_doc.payment_entry = payment_entry.name
        log_doc.status = "Success"
        log_doc.save(ignore_permissions=True)
        frappe.db.commit()

    except Exception:
        frappe.db.rollback()
        error_text = traceback.format_exc()
        
        frappe.get_doc("Payment Webhook Log", log_name).db_set({
            "status": "Failed",
            "error_message": error_text
        })
    finally:
        if original_user:
            frappe.set_user(original_user)