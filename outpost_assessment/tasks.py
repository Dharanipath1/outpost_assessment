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

