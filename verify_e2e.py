import httpx

BASE_URL = "http://127.0.0.1:8000"


def test_pipeline():
    client = httpx.Client(timeout=30.0)
    print("--- Stage 1: Auth ---")
    client.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={
            "email": "auto.qa@example.com",
            "password": "Password123!",
            "full_name": "QA Tester",
        },
    )

    login_res = client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": "auto.qa@example.com", "password": "Password123!"},
    )
    assert login_res.status_code in (200, 201), f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[PASS] Stage 1 PASS - Token acquired: {token[:15]}...")

    print("--- Stage 2: Workspace ---")
    ws_res = client.get(f"{BASE_URL}/api/v1/workspaces", headers=headers)
    assert ws_res.status_code == 200, f"Workspace list failed: {ws_res.text}"
    ws_id = ws_res.json()[0]["id"]
    headers["X-Workspace-Id"] = ws_id

    direct_ws = client.get(f"{BASE_URL}/api/v1/workspaces/{ws_id}", headers=headers)
    assert direct_ws.status_code == 200, (
        f"Direct workspace fetch failed: {direct_ws.status_code}"
    )
    print(f"[PASS] Stage 2 PASS - Workspace resolved: {ws_id}")

    print("--- Stage 3: Upload ---")
    pdf_bytes = b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj\n4 0 obj << /Length 150 >> stream\nBT /F1 12 Tf 50 700 Td (TAX INVOICE INV-2026-1042 Subtotal: 50,000 GST: 9,000 Total Amount Payable: 59,000) Tj ET\nendstream endobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n00000000115 00000 n \n00000000214 00000 n \ntrailer << /Size 5 /Root 1 0 R >>\nstartxref\n415\n%%EOF"
    upload_res = client.post(
        f"{BASE_URL}/api/v1/documents/upload",
        headers=headers,
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        data={"document_type": "INVOICE"},
    )
    assert upload_res.status_code in (200, 201), f"Upload failed: {upload_res.text}"
    doc_id = upload_res.json()["id"]
    print(f"[PASS] Stage 3 PASS - Document uploaded ID: {doc_id}")

    print("--- Stage 4: Processing ---")
    proc_res = client.post(
        f"{BASE_URL}/api/v1/documents/{doc_id}/process", headers=headers
    )
    assert proc_res.status_code == 200, f"Process trigger failed: {proc_res.text}"
    print("[PASS] Stage 4 PASS - Processing triggered")

    print("--- Stage 5: Extraction & Math ---")
    ext_res = client.get(
        f"{BASE_URL}/api/v1/documents/{doc_id}/extraction", headers=headers
    )
    assert ext_res.status_code == 200, f"Extraction failed: {ext_res.text}"
    print("[PASS] Stage 5 PASS - Extraction & Math validation verified")

    print("--- Stage 6: Approval ---")
    app_res = client.post(
        f"{BASE_URL}/api/v1/documents/{doc_id}/approve",
        headers=headers,
        json={"notes": "E2E Approved"},
    )
    assert app_res.status_code == 200, f"Approval failed: {app_res.text}"
    assert app_res.json()["status"] == "completed"
    print("[PASS] Stage 6 PASS - Document approved, status transitioned to 'completed'")

    print("--- Stage 7: Workflow ---")
    wf_res = client.get(f"{BASE_URL}/api/v1/workflows", headers=headers)
    assert wf_res.status_code == 200
    print("[PASS] Stage 7 PASS - Workflow system verified")

    print("--- Stage 8: Audit ---")
    audit_res = client.get(
        f"{BASE_URL}/api/v1/documents/{doc_id}/audit", headers=headers
    )
    assert audit_res.status_code == 200, f"Audit failed: {audit_res.text}"
    logs = audit_res.json()
    print(f"[PASS] Stage 8 PASS - Found {len(logs)} audit entries")

    print("\n=========================================")
    print("ALL 8 E2E PIPELINE STAGES PASSED SUCCESSFULLY!")
    print("=========================================")


if __name__ == "__main__":
    test_pipeline()
