import time
import uuid

import httpx

BASE_URL = "http://127.0.0.1:8000"


def run_workflow_e2e():
    client = httpx.Client(timeout=30.0)
    print("=================================================================")
    print("   DOCUMENT INTELLIGENCE & WORKFLOW AUTOMATION E2E TEST RUNNER   ")
    print("=================================================================")

    # 1. Auth & Workspace
    print("\n[Step 1] Authenticating User & Resolving Workspace...")
    email = f"wf.tester.{uuid.uuid4().hex[:6]}@example.com"
    client.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Workflow QA Lead",
        },
    )
    login_res = client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = client.get(f"{BASE_URL}/api/v1/workspaces", headers=headers)
    assert ws_res.status_code == 200, f"Workspaces failed: {ws_res.text}"
    ws_id = ws_res.json()[0]["id"]
    headers["X-Workspace-Id"] = ws_id
    print(f" -> Logged in as: {email}")
    print(f" -> Active Workspace ID: {ws_id}")

    # 2. Register Workflows
    print("\n[Step 2] Configuring Automated Workflows...")
    # WF 1: On Extraction
    wf1_res = client.post(
        f"{BASE_URL}/api/v1/workflows",
        headers=headers,
        json={
            "name": "E2E Extraction High-Value Router",
            "description": "Routes invoices over $1000 and posts notification",
            "trigger_type": "ON_DOCUMENT_EXTRACTED",
            "is_active": True,
            "conditions": {
                "all": [{"field": "total", "operator": ">=", "value": 50000}]
            },
            "actions": [
                {
                    "type": "NOTIFICATION",
                    "name": "Finance Notification",
                    "params": {
                        "channel": "finance-slack",
                        "message": "High-value invoice {{invoice_number}} from {{vendor_name}} extracted: ${{total}}",
                    },
                }
            ],
        },
    )
    assert wf1_res.status_code in (200, 201), f"WF1 creation failed: {wf1_res.text}"
    wf1_id = wf1_res.json()["id"]
    print(f" -> Created Workflow 1 (Trigger: ON_DOCUMENT_EXTRACTED, ID: {wf1_id})")

    # WF 2: On Approval
    wf2_res = client.post(
        f"{BASE_URL}/api/v1/workflows",
        headers=headers,
        json={
            "name": "E2E Approval ERP Sync",
            "description": "Updates metadata and notifies downstream ERP",
            "trigger_type": "ON_DOCUMENT_APPROVED",
            "is_active": True,
            "conditions": {},
            "actions": [
                {
                    "type": "DATABASE_UPDATE",
                    "name": "Set ERP Synced Flag",
                    "params": {
                        "status": "completed",
                        "metadata": {"erp_synced": True, "sync_batch": "BATCH-2026-QA"},
                    },
                },
                {
                    "type": "NOTIFICATION",
                    "name": "ERP Dispatch Notification",
                    "params": {
                        "channel": "erp-queue",
                        "message": "Invoice {{invoice_number}} synced to ERP successfully",
                    },
                },
            ],
        },
    )
    assert wf2_res.status_code in (200, 201), f"WF2 creation failed: {wf2_res.text}"
    wf2_id = wf2_res.json()["id"]
    print(f" -> Created Workflow 2 (Trigger: ON_DOCUMENT_APPROVED, ID: {wf2_id})")

    # 3. Upload Document
    print("\n[Step 3] Uploading Multi-Line Tax Invoice...")
    pdf_bytes = b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj\n4 0 obj << /Length 150 >> stream\nBT /F1 12 Tf 50 700 Td (TAX INVOICE INV-2026-9901 Subtotal: 50,000 GST: 9,000 Total Amount Payable: 59,000) Tj ET\nendstream endobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n00000000115 00000 n \n00000000214 00000 n \ntrailer << /Size 5 /Root 1 0 R >>\nstartxref\n415\n%%EOF"
    upload_res = client.post(
        f"{BASE_URL}/api/v1/documents/upload",
        headers=headers,
        files={"file": ("tax_invoice_2026.pdf", pdf_bytes, "application/pdf")},
        data={"document_type": "INVOICE"},
    )
    assert upload_res.status_code in (200, 201), f"Upload failed: {upload_res.text}"
    doc_id = upload_res.json()["id"]
    print(f" -> Uploaded Document ID: {doc_id}")

    # 4. Trigger Processing & Verify Extraction
    print("\n[Step 4] Executing OCR & Extraction Pipeline...")
    proc_res = client.post(
        f"{BASE_URL}/api/v1/documents/{doc_id}/process", headers=headers
    )
    assert proc_res.status_code == 200, f"Process trigger failed: {proc_res.text}"

    # Poll for extraction completion
    doc_status = "processing"
    for _ in range(20):
        doc_res = client.get(f"{BASE_URL}/api/v1/documents/{doc_id}", headers=headers)
        if doc_res.status_code == 200:
            doc_status = doc_res.json().get("status")
            if doc_status in ["completed", "review_required", "failed"]:
                break
        time.sleep(0.3)
    print(f" -> OCR & Structured Extraction Complete (Doc Status: {doc_status})")

    # 5. Verify Workflow 1 Execution (ON_DOCUMENT_EXTRACTED)
    print(
        "\n[Step 5] Checking Automated Execution of Workflow 1 (ON_DOCUMENT_EXTRACTED)..."
    )
    wf1_execs = client.get(
        f"{BASE_URL}/api/v1/workflows/{wf1_id}/executions", headers=headers
    )
    assert wf1_execs.status_code == 200
    exec_list_1 = wf1_execs.json()
    assert len(exec_list_1) >= 1, "Workflow 1 execution was not triggered!"
    latest_exec_1 = exec_list_1[0]
    print(f" -> Workflow 1 Execution ID: {latest_exec_1['id']}")
    print(f" -> Status: {latest_exec_1['status']}")
    print(
        f" -> Execution Logs: {len(latest_exec_1.get('execution_logs') or [])} entries recorded"
    )
    for log in latest_exec_1.get("execution_logs") or []:
        print(f"    [{log.get('level')}] {log.get('message')}")
    assert latest_exec_1["status"] == "COMPLETED"

    # 6. Approve Document
    print("\n[Step 6] Approving Document in HITL Review Workbench...")
    app_res = client.post(
        f"{BASE_URL}/api/v1/documents/{doc_id}/approve",
        headers=headers,
        json={"notes": "Audited and approved by Senior QA Lead"},
    )
    assert app_res.status_code == 200, f"Approval failed: {app_res.text}"
    print(f" -> Document Status Transitioned: {app_res.json()['status']}")

    # 7. Verify Workflow 2 Execution (ON_DOCUMENT_APPROVED)
    print(
        "\n[Step 7] Checking Automated Execution of Workflow 2 (ON_DOCUMENT_APPROVED)..."
    )
    wf2_execs = client.get(
        f"{BASE_URL}/api/v1/workflows/{wf2_id}/executions", headers=headers
    )
    assert wf2_execs.status_code == 200
    exec_list_2 = wf2_execs.json()
    assert len(exec_list_2) >= 1, "Workflow 2 execution was not triggered!"
    latest_exec_2 = exec_list_2[0]
    print(f" -> Workflow 2 Execution ID: {latest_exec_2['id']}")
    print(f" -> Status: {latest_exec_2['status']}")
    for log in latest_exec_2.get("execution_logs") or []:
        print(f"    [{log.get('level')}] {log.get('message')}")
    assert latest_exec_2["status"] == "COMPLETED"

    # 8. Check Document & Audit History
    print("\n[Step 8] Verifying Audit Trail Integrity...")
    audit_res = client.get(
        f"{BASE_URL}/api/v1/documents/{doc_id}/audit", headers=headers
    )
    assert audit_res.status_code == 200
    logs = audit_res.json()
    print(f" -> Total Immutable Audit Entries: {len(logs)}")
    for entry in logs:
        print(f"    [{entry['action']}] by User {entry['user_id']}")

    print("\n=================================================================")
    print("   [SUCCESS] ALL WORKFLOW AUTOMATION PIPELINE TESTS PASSED 100%!  ")
    print("=================================================================")


if __name__ == "__main__":
    run_workflow_e2e()
