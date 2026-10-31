import io

import pytest
from backend.app.models.workspace import Workspace
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_document_upload_and_lifecycle(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace: Workspace,
):
    """Test uploading a document, listing, reading, downloading, and deleting."""
    # 1. Upload mock PDF document
    dummy_pdf_content = b"%PDF-1.5 Mock PDF Content for document intelligence"
    files = {"file": ("invoice_sample.pdf", io.BytesIO(dummy_pdf_content), "application/pdf")}
    data = {
        "document_type": "INVOICE",
    }

    upload_res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        data=data,
        headers=auth_headers,
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["original_filename"] == "invoice_sample.pdf"
    assert doc_data["document_type"] == "INVOICE"
    assert doc_data["status"] == "uploaded"
    doc_id = doc_data["id"]

    # 2. List documents
    list_res = await client.get("/api/v1/documents", headers=auth_headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["id"] == doc_id

    # 3. Get single document
    get_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id

    # 4. Download document
    download_res = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers)
    assert download_res.status_code == 200
    assert download_res.content == dummy_pdf_content

    # 5. Delete document
    del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # Verify deleted
    get_after_del = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_document_upload_any_format(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace: Workspace,
):
    """Test that the flexible 'any format' endpoint accepts a non-PDF,
    non-image file (e.g. a .txt file) without raising a validation error,
    while the strict /upload endpoint would normally reject it."""
    dummy_text_content = b"This is a plain text file, not a PDF or image."
    files = {
        "file": ("notes.txt", io.BytesIO(dummy_text_content), "text/plain"),
    }
    data = {
        "document_type": "UNKNOWN",
    }

    upload_res = await client.post(
        "/api/v1/documents/upload-any",
        files=files,
        data=data,
        headers=auth_headers,
    )

    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["original_filename"] == "notes.txt"
    assert doc_data["status"] == "uploaded"

    # Confirm it's retrievable like any other document
    doc_id = doc_data["id"]
    get_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_strict_pdf_upload_still_rejects_other_formats(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace: Workspace,
):
    """Confirm the original strict /upload endpoint's PDF-only validation is unaffected."""
    dummy_text_content = b"Not a real PDF."
    files = {
        "file": ("notes.txt", io.BytesIO(dummy_text_content), "text/plain"),
    }
    data = {
        "document_type": "UNKNOWN",
    }

    upload_res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        data=data,
        headers=auth_headers,
    )

    assert upload_res.status_code == 422


@pytest.mark.asyncio
async def test_documents_export_csv(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace: Workspace,
):
    """Verify CSV export functionality per PRD Section 20/32."""
    # 1. Upload a document
    dummy_pdf_content = b"%PDF-1.5 Mock PDF for CSV export test"
    files = {"file": ("export_test.pdf", io.BytesIO(dummy_pdf_content), "application/pdf")}
    await client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"document_type": "INVOICE"},
        headers=auth_headers,
    )

    # 2. Export CSV
    export_res = await client.get("/api/v1/documents/export/csv", headers=auth_headers)
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    csv_text = export_res.text
    assert "filename" in csv_text
    assert "export_test.pdf" in csv_text


@pytest.mark.asyncio
async def test_document_export_erp_formats(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace: Workspace,
):
    """Test ERP data export in JSON, CSV, and TXT formats for document intelligence integration."""
    dummy_pdf_content = b"%PDF-1.5 Mock PDF for ERP Export Test"
    files = {"file": ("erp_invoice.pdf", io.BytesIO(dummy_pdf_content), "application/pdf")}
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"document_type": "INVOICE"},
        headers=auth_headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 1. Test JSON ERP export
    res_json = await client.get(
        f"/api/v1/documents/{doc_id}/export-erp?format=json", headers=auth_headers
    )
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    json_data = res_json.json()
    assert json_data["document_id"] == doc_id
    assert json_data["filename"] == "erp_invoice.pdf"

    # 2. Test CSV ERP export
    res_csv = await client.get(
        f"/api/v1/documents/{doc_id}/export-erp?format=csv", headers=auth_headers
    )
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Document_ID" in res_csv.text

    # 3. Test TXT ERP export
    res_txt = await client.get(
        f"/api/v1/documents/{doc_id}/export-erp?format=txt", headers=auth_headers
    )
    assert res_txt.status_code == 200
    assert "text/plain" in res_txt.headers["content-type"]
    assert "ERP DOCUMENT EXTRACTION EXPORT" in res_txt.text


@pytest.mark.asyncio
async def test_document_audit_pdf_export(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace: Workspace,
):
    """Verify the Audit tab PDF route returns a valid downloadable PDF."""
    files = {
        "file": ("audit_invoice.pdf", io.BytesIO(b"%PDF-1.5 Audit PDF test"), "application/pdf")
    }
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"document_type": "INVOICE"},
        headers=auth_headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    export_res = await client.get(f"/api/v1/documents/{doc_id}/export-pdf", headers=auth_headers)
    assert export_res.status_code == 200
    assert export_res.headers["content-type"].startswith("application/pdf")
    assert "audit_invoice_audit_report.pdf" in export_res.headers["content-disposition"]
    assert export_res.content.startswith(b"%PDF-1.4")
