import io
import zipfile

from app import certificate


def create(client, payload):
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    return response.json()["job_id"]


def test_create_job_and_get_progress(client, payload):
    job_id = create(client, payload)
    result = client.get(f"/api/v1/jobs/{job_id}")
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "completed"
    assert body["total_count"] == 2
    assert body["successful_count"] == 2
    assert body["failed_count"] == body["pending_count"] == 0
    assert all(item["status"] == "success" for item in body["recipients"])


def test_request_validation_and_invalid_recipient_partial_success(client, payload):
    assert client.post("/api/v1/jobs", json={}).status_code == 422
    payload["recipients"] = [{"name": "   "}, {"name": "Valid", "email": "valid@example.com"}, {"name": "Bad email", "email": "nope"}]
    job_id = create(client, payload)
    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["status"] == "completed_with_errors"
    assert body["successful_count"] == 1
    assert body["failed_count"] == 2
    assert all(r["error_message"] for r in body["recipients"] if r["status"] == "failed")


def test_generated_pdf_contains_recipient_content(client, payload):
    job_id = create(client, payload)
    info = client.get(f"/api/v1/jobs/{job_id}").json()
    recipient = info["recipients"][0]
    pdf = client.get(f"/api/v1/jobs/{job_id}/certificates/{recipient['id']}")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert b"Alice Johnson" in pdf.content


def test_one_generation_failure_does_not_stop_others(client, payload, monkeypatch):
    original = certificate.generate_certificate

    def fail_bob(path, title, name, event, issuer, issue_date):
        if name == "Bob Smith":
            raise OSError("simulated filesystem failure")
        original(path, title, name, event, issuer, issue_date)

    monkeypatch.setattr(certificate, "generate_certificate", fail_bob)
    job_id = create(client, payload)
    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["status"] == "completed_with_errors"
    assert body["successful_count"] == body["failed_count"] == 1


def test_download_pdf_and_zip(client, payload):
    job_id = create(client, payload)
    body = client.get(f"/api/v1/jobs/{job_id}").json()
    recipient_id = body["recipients"][0]["id"]
    assert client.get(f"/api/v1/jobs/{job_id}/certificates/{recipient_id}").status_code == 200
    response = client.get(f"/api/v1/jobs/{job_id}/certificates")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert len(archive.namelist()) == 2


def test_unknown_and_unavailable_files(client, payload, tmp_path, monkeypatch):
    assert client.get("/api/v1/jobs/no-such-job").status_code == 404
    job_id = create(client, payload)
    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert client.get(f"/api/v1/jobs/{job_id}/certificates/no-recipient").status_code == 404
    recipient_id = body["recipients"][0]["id"]
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "missing"))
    assert client.get(f"/api/v1/jobs/{job_id}/certificates/{recipient_id}").status_code == 404


def test_zip_when_no_success_is_available(client, payload, monkeypatch):
    monkeypatch.setattr(certificate, "generate_certificate", lambda *args: (_ for _ in ()).throw(OSError()))
    job_id = create(client, payload)
    assert client.get(f"/api/v1/jobs/{job_id}/certificates").status_code == 404
