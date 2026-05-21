# Outpost Assessment — Custom ERPNext Modules

**Custom App:** `outpost_assessment`  
**Framework:** Frappe v15 / ERPNext v15  
**Site:** `test` (`test.pontuserp.com`)

---

# T1 — ERPNext Manufacturing Workflow Automation

## Overview

This module automates the production planning and material reservation process for corrugated box manufacturing. It introduces a custom `Production Request` DocType that acts as the trigger for the entire manufacturing workflow.

## Features

1. **Production Request DocType**:
   - Captures `Customer`, `Item`, `Quantity`, `Required Date`, and `Priority`.
   - Fetches the default BOM for the item automatically.
2. **Automated Validation & Material Reservation**:
   - On submission, validates that a standard BOM exists for the selected Item.
   - Automatically creates a `Work Order` in the background.
   - Reserves required raw materials automatically.
   - **Shortage Protection:** If stock is insufficient, it actively blocks submission and displays a detailed shortage table showing exactly what materials are missing.
3. **Dashboards**:
   - Includes a custom dashboard/report to track `Pending Production`, `Completed Production`, and `Material Shortages`.
4. **Delayed Work Order Reminders**:
   - A background daily scheduler job (`send_delayed_work_order_reminders`) monitors `Work Orders`.
   - Automatically sends an email with a compiled Excel attachment of delayed orders to users with the **Manufacturing Manager** role if the `expected_delivery_date` has passed.

## Setup Instructions

### 1. Install and Migrate

```bash
bench --site test migrate
```

### 2. Configure Roles

Ensure that the users responsible for receiving delay notifications have the **Manufacturing Manager** role assigned to them in ERPNext and have a valid email address.

### 3. Usage

1. Navigate to the **Production Request** list in ERPNext Desk.
2. Click **Add Production Request**.
3. Select the Customer and the Item (ensure the Item has a valid standard BOM).
4. Enter the Quantity and Required Date.
5. Save and Submit.
   - If stock is short, a validation error will pop up displaying the exact missing items and quantities.
   - If stock is available, it successfully submits, creating a Work Order and reserving stock instantly.

## File Structure (T1)

```
outpost_assessment/
└── outpost_assessment/
    ├── doctype/
    │   ├── production_request/
    │   ├── production_request_item/
    │   ├── production_request_material/
    │   └── production_request_sub_assembly/
    ├── tasks.py                    # Contains `send_delayed_work_order_reminders`
    ├── hooks.py                    # Daily scheduler configuration
    └── overrides/
        ├── work_order.py           # Dashboard overrides
        └── stock_entry.py
```

---

# T2 — ERPNext Payment Gateway Integration


## Overview

This module implements a production-grade, enterprise-secure payment webhook receiver inside the `outpost_assessment` Frappe custom app.

When a payment gateway (e.g. Razorpay, Stripe, Cashfree) sends a webhook notification to the endpoint, the system:

1. **Authenticates** the request using HMAC-SHA256 signature verification
2. **Checks for duplicates** before doing any write (idempotency)
3. **Saves a log record** (`Payment Webhook Log`) with status `Pending`
4. **Dispatches a background worker** that creates a `Payment Entry` and marks the invoice as paid
5. **Retries failed transactions** automatically every hour (up to 3 attempts)

---

## Architecture

```
HTTP POST /api/method/outpost_assessment.api.payment.update_status
          │
          ▼
  [HMAC-SHA256 Signature Validation]
          │ ✓
          ▼
  [Idempotency Check — Payment Webhook Log.transaction_id is UNIQUE]
          │ new
          ▼
  [Insert Payment Webhook Log — status: Pending]
          │
          ▼
  [frappe.enqueue → background job]
          │
          └── process_payment_webhook()
                │
                ├── payload.status != "success" → status: Failed
                │
                ├── invoice.outstanding_amount <= 0 → status: Failed
                │
                └── create + submit Payment Entry → status: Success

  [Hourly Scheduler] → retry_failed_webhooks()
          │
          └── re-enqueue logs where status=Failed, retry_count < 3
```

---

## File Structure

```
outpost_assessment/
└── outpost_assessment/
    ├── hooks.py                                    # Scheduler registration
    ├── tasks.py                                    # retry_failed_webhooks()
    ├── setup_doctypes.py                           # Programmatic DocType creator
    ├── api/
    │   ├── __init__.py
    │   └── payment.py                             # Webhook endpoint + worker
    └── outpost_assessment/
        └── doctype/
            ├── payment_gateway_settings/
            │   ├── payment_gateway_settings.json  # Single DocType definition
            │   └── payment_gateway_settings.py
            └── payment_webhook_log/
                ├── payment_webhook_log.json        # Log DocType definition
                └── payment_webhook_log.py
```

---

## DocTypes

### `Payment Gateway Settings` (Single)

Stores site-wide configuration. Accessible via **Settings → Payment Gateway Settings** in the ERPNext desk.

| Field | Type | Purpose |
|---|---|---|
| `is_enabled` | Check | Master on/off switch |
| `webhook_secret` | Password | HMAC-SHA256 shared secret (encrypted at rest) |

### `Payment Webhook Log`

One record per inbound webhook call. `transaction_id` is marked `unique` at both the application and database level.

| Field | Type | Purpose |
|---|---|---|
| `transaction_id` | Data (Unique) | Idempotency key |
| `status` | Select | Pending / Processing / Success / Failed |
| `amount` | Currency | Payment amount from payload |
| `currency` | Data | Default: INR |
| `invoice_id` | Link → Sales Invoice | Invoice being paid |
| `payment_entry` | Link → Payment Entry | Created on success |
| `retry_count` | Int | Incremented on each retry (capped at 3) |
| `raw_payload` | Long Text | Full JSON stored for audit |
| `error_message` | Long Text | Full traceback on failure |

---

## Security Design

### HMAC-SHA256 Signature Verification

Every inbound request must include the header:

```
X-Signature: hmac-sha256=<hex_digest>
```

The digest is computed by the gateway as:

```python
import hashlib, hmac, json
secret = "outpost-hmac-secret-2026"
body   = json.dumps(payload, separators=(",", ":"))   # compact, key-order matters
mac    = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
header = f"hmac-sha256={mac}"
```

The server replicates the same computation over the **raw request body** and compares using `hmac.compare_digest` — a constant-time comparison that prevents timing-oracle attacks.

Requests with missing or mismatched signatures receive `HTTP 401` immediately, before any database interaction.

### Encrypted Secret Storage

`webhook_secret` is stored as a Frappe `Password` fieldtype, which encrypts the value using Fernet symmetric encryption tied to the site's `encryption_key`. It is never written to logs.

---

## Idempotency Design

Payment gateways routinely deliver webhooks more than once (network retries, at-least-once delivery). The system handles this at two layers:

1. **Application layer**: Before any write, `frappe.db.exists("Payment Webhook Log", {"transaction_id": transaction_id})` is checked. If found, the function returns `{"status": "duplicate"}` immediately.
2. **Database layer**: The `transaction_id` field has `unique: 1` in the DocType JSON, creating a MySQL `UNIQUE` constraint. If two concurrent requests with the same transaction_id bypass the application check simultaneously, the second `INSERT` will fail at the DB level, preventing double-processing.

---

## Retry Mechanism

The `retry_failed_webhooks()` function runs **hourly** via `scheduler_events` in `hooks.py`.

```python
scheduler_events = {
    "hourly": ["outpost_assessment.tasks.retry_failed_webhooks"],
}
```

**Logic:**
- Query logs where `status = "Failed"` AND `retry_count < 3`
- Re-enqueue each as a separate background job
- Logs that have failed 3 or more times are left in `Failed` state for manual review

To trigger manually (without waiting for the hourly schedule):

```bash
bench --site test execute outpost_assessment.tasks.retry_failed_webhooks
```

---

## Setup Instructions

### 1. Install and Migrate

```bash
bench --site test migrate
```

### 2. Create DocTypes Programmatically

```bash
bench --site test execute outpost_assessment.setup_doctypes.execute
```

> DocTypes are also created automatically by `bench migrate` reading the JSON fixture files. This script is idempotent — it skips creation if DocTypes already exist.

### 3. Configure the Gateway

Open **Settings → Payment Gateway Settings** in the ERPNext desk:

- Enable **Is Enabled** ✓
- Set **Webhook Secret** to the same secret configured in your payment gateway dashboard (e.g. `outpost-hmac-secret-2026`)
- Save

Or via bench console:

```python
s = frappe.get_single("Payment Gateway Settings")
s.is_enabled = 1
s.webhook_secret = "outpost-hmac-secret-2026"
s.save()
frappe.db.commit()
```



## API Reference

### Endpoint

```
POST https://test.pontuserp.com/api/method/outpost_assessment.api.payment.update_status
```

### Headers

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-Signature` | `hmac-sha256=<hex_digest>` |

### Payload Schema

```json
{
  "transaction_id": "TXN-ABC-001",
  "status": "success",
  "amount": 1000.0,
  "currency": "INR",
  "invoice_id": "ACC-SINV-2026-00001"
}
```

| Field | Required | Description |
|---|---|---|
| `transaction_id` | Yes | Unique identifier from gateway — used as idempotency key |
| `status` | Yes | `"success"` triggers Payment Entry creation; any other value marks log Failed |
| `amount` | Yes | Payment amount in the specified currency |
| `currency` | No | Default: `INR` |
| `invoice_id` | Yes | Exact name of the submitted Sales Invoice in ERPNext |

### Responses

| Scenario | HTTP | Body |
|---|---|---|
| New, valid webhook | 200 | `{"status": "queued", "log": "TXN-ABC-001"}` |
| Duplicate transaction_id | 200 | `{"status": "duplicate", "message": "Transaction already processed."}` |
| Invalid/missing signature | 401 | `{"status": "error", "message": "Invalid signature."}` |
| Gateway disabled | 403 | Frappe PermissionError response |
| Invalid JSON body | 417 | Frappe ValidationError response |

---

## Postman Testing

### 1 — Successful Payment

```
POST https://test.pontuserp.com/api/method/outpost_assessment.api.payment.update_status
Headers:
  Content-Type: application/json
  X-Signature: hmac-sha256=<your_computed_hmac>
Body:
  {"transaction_id":"TXN-TEST-001","status":"success","amount":1000.0,"currency":"INR","invoice_id":"<invoice_name>"}
```

**Expected:** `{"status": "queued"}` → Check Payment Webhook Log, then Payment Entry after ~5 seconds.

### 2 — Duplicate Payment (Idempotency Test)

Send the **identical payload and headers** from Test 1 again.

**Expected:** `{"status": "duplicate"}` — No second Payment Entry created.

### 3 — Failed Payment

```json
{"transaction_id":"TXN-TEST-002","status":"failed","amount":1000.0,"currency":"INR","invoice_id":"<invoice_name>"}
```

**Expected:** `{"status": "queued"}` → Log status becomes `Failed` (gateway reported failure).

---

## Monitoring

Navigate to **Outpost Assessment → Payment Webhook Log** in the ERPNext desk to:

- View all inbound webhooks with their status
- Inspect the raw payload for any log
- Read the full error traceback for Failed logs
- Monitor retry counts

---

## Edge Cases Handled

| Scenario | Handling |
|---|---|
| Duplicate webhook delivery | Application + DB unique constraint |
| Race condition (two simultaneous identical webhooks) | DB-level UNIQUE on `transaction_id` |
| Invoice already fully paid | `outstanding_amount <= 0` check before PE creation |
| Gateway sends `status: failed` | Log marked Failed; no Payment Entry created |
| Background worker crashes mid-flight | `try/except` → `db.rollback()` → status Failed → hourly retry |
| Persistent failure after 3 retries | Log stays Failed; manual review required |
| Missing `invoice_id` in payload | Immediate failure with clear error message |
| Tampered payload | HMAC mismatch → HTTP 401, no DB write |
| `webhook_secret` not set | `get_password()` raises exception caught at endpoint level |

---
