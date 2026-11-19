import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tools.artifact_gateway import app as gateway_module
from tools.artifact_gateway.app import Settings, create_app


API_KEY = "test-secret-key-that-is-long-enough-for-the-gateway"


@pytest.fixture
def gateway(tmp_path):
    settings = Settings(
        project_id="nexora",
        api_key=API_KEY,
        root=tmp_path.resolve(),
        max_upload_bytes=1024 * 1024,
    )
    return TestClient(create_app(settings))


def auth():
    return {"Authorization": f"Bearer {API_KEY}"}


def test_health_is_available_without_auth(gateway):
    response = gateway.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_text_returns_hash_and_extracted_text(gateway):
    payload = b"TRADIX artifact gateway"
    response = gateway.post(
        "/v1/artifacts",
        headers={**auth(), "X-Content-SHA256": hashlib.sha256(payload).hexdigest()},
        files={"file": ("notes.txt", payload, "text/plain")},
    )
    assert response.status_code == 201
    receipt = response.json()
    assert receipt["project_id"] == "nexora"
    assert receipt["sha256"] == hashlib.sha256(payload).hexdigest()
    assert receipt["extraction"]["text"] == payload.decode()


def test_receipt_is_retrievable_and_project_scoped(gateway):
    response = gateway.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("memo.md", b"# hello", "text/markdown")},
    )
    artifact_id = response.json()["artifact_id"]
    fetched = gateway.get(f"/v1/artifacts/{artifact_id}", headers=auth())
    assert fetched.status_code == 200
    assert fetched.json()["artifact_id"] == artifact_id
    assert fetched.json()["project_id"] == "nexora"


def test_upload_rejects_missing_or_invalid_auth(gateway):
    payload = {"file": ("x.txt", b"x", "text/plain")}
    assert gateway.post("/v1/artifacts", files=payload).status_code == 401
    assert gateway.post(
        "/v1/artifacts", headers={"Authorization": "Bearer wrong"}, files=payload
    ).status_code == 401


def test_upload_rejects_hash_mismatch(gateway):
    response = gateway.post(
        "/v1/artifacts",
        headers={**auth(), "X-Content-SHA256": "0" * 64},
        files={"file": ("x.txt", b"real content", "text/plain")},
    )
    assert response.status_code == 422
    assert "SHA-256 mismatch" in response.text


def test_upload_rejects_oversized_body(gateway):
    response = gateway.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("large.bin", b"x" * (1024 * 1024 + 1), "application/octet-stream")},
    )
    assert response.status_code == 413


def test_upload_rejects_corrupt_zip(gateway):
    response = gateway.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("broken.zip", b"not a zip archive", "application/zip")},
    )
    assert response.status_code == 422


def test_upload_sanitizes_filename_and_deduplicates_content(gateway):
    payload = b"same bytes"
    first = gateway.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("../../private.txt", payload, "text/plain")},
    ).json()
    second = gateway.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("renamed.txt", payload, "text/plain")},
    ).json()
    assert first["filename"] == "private.txt"
    assert first["storage_ref"] == second["storage_ref"]
    assert first["artifact_id"] != second["artifact_id"]


def test_s3_backend_upload_is_verified(monkeypatch, tmp_path):
    class FakeS3:
        def __init__(self):
            self.objects = {}

        def put_object(self, Bucket, Key, Body, ContentLength, Metadata):
            data = Body.read()
            self.objects[(Bucket, Key)] = {"data": data, "Metadata": Metadata}
            assert len(data) == ContentLength

        def head_object(self, Bucket, Key):
            item = self.objects[(Bucket, Key)]
            return {
                "ContentLength": len(item["data"]),
                "Metadata": item["Metadata"],
            }

        def get_object(self, Bucket, Key):
            import io
            return {"Body": io.BytesIO(self.objects[(Bucket, Key)]["data"])}

    fake = FakeS3()
    monkeypatch.setattr(gateway_module, "_s3_client", lambda settings: fake)
    settings = Settings(
        project_id="nexora",
        api_key=API_KEY,
        root=tmp_path.resolve(),
        storage_backend="s3",
        s3_endpoint_url="https://s3.example.invalid",
        s3_region="us-east-005",
        s3_bucket="nexora-private",
        s3_access_key_id="not-a-real-key",
        s3_secret_access_key="not-a-real-secret",
    )
    client = TestClient(create_app(settings))
    payload = b"stored remotely"
    response = client.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("payload.bin", payload, "application/octet-stream")},
    )
    assert response.status_code == 201
    receipt = response.json()
    assert receipt["storage_backend"] == "s3"
    assert receipt["storage_ref"].startswith("s3://nexora-private/projects/nexora/")
    assert next(iter(fake.objects.values()))["data"] == payload


def test_github_backend_uploads_and_verifies_readback(monkeypatch, tmp_path):
    import io
    import base64
    from tools.artifact_gateway import github_storage

    stored = {}
    requested_get_urls = []

    def fake_urlopen(request, timeout=30):
        if request.method == "GET":
            requested_get_urls.append(request.full_url)
        if request.method == "PUT":
            payload = json.loads(request.data.decode("utf-8"))
            stored["bytes"] = base64.b64decode(payload["content"])
            path = request.full_url.split("/contents/", 1)[1]
            return io.BytesIO(json.dumps({
                "content": {"path": path},
                "commit": {"sha": "a" * 40},
            }).encode("utf-8"))
        if "bytes" not in stored:
            raise github_storage.urllib.error.HTTPError(
                request.full_url, 404, "Not Found", None, io.BytesIO(b"")
            )
        return io.BytesIO(stored["bytes"])

    monkeypatch.setattr(github_storage.urllib.request, "urlopen", fake_urlopen)
    settings = Settings(
        project_id="nexora",
        api_key=API_KEY,
        root=tmp_path.resolve(),
        storage_backend="github",
        github_repository="grinlife4-stack/NEXORA",
        github_branch="artifact-intake",
        github_path_prefix="incoming-artifacts",
        github_token="ghp_" + "x" * 36,
    )
    client = TestClient(create_app(settings))
    payload = b"verified binary artifact"
    response = client.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("bundle.bin", payload, "application/octet-stream")},
    )
    assert response.status_code == 201
    receipt = response.json()
    assert receipt["storage_backend"] == "github"
    assert receipt["remote_commit_sha"] == "a" * 40
    assert receipt["sha256"] == hashlib.sha256(payload).hexdigest()
    assert stored["bytes"] == payload
    assert requested_get_urls
    assert all("ref=artifact-intake" in url for url in requested_get_urls)
    assert "github_token" not in json.dumps(receipt)
    repeated = client.post(
        "/v1/artifacts",
        headers=auth(),
        files={"file": ("same-bundle.bin", payload, "application/octet-stream")},
    )
    assert repeated.status_code == 201
    assert repeated.json()["storage_ref"] == receipt["storage_ref"]
    assert repeated.json()["remote_commit_sha"] is None


def test_settings_reads_max_upload_bytes(monkeypatch, tmp_path):
    monkeypatch.setenv("TRADIX_PROJECT_ID", "tradix-test")
    monkeypatch.setenv("TRADIX_API_KEY", API_KEY)
    monkeypatch.setenv("TRADIX_ARTIFACT_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv("TRADIX_MAX_UPLOAD_BYTES", "12345")
    monkeypatch.setenv("TRADIX_STORAGE_BACKEND", "local")
    assert Settings.from_env().max_upload_bytes == 12345


def test_settings_rejects_invalid_max_upload_bytes(monkeypatch, tmp_path):
    monkeypatch.setenv("TRADIX_PROJECT_ID", "tradix-test")
    monkeypatch.setenv("TRADIX_API_KEY", API_KEY)
    monkeypatch.setenv("TRADIX_ARTIFACT_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv("TRADIX_MAX_UPLOAD_BYTES", "not-an-integer")
    monkeypatch.setenv("TRADIX_STORAGE_BACKEND", "local")
    with pytest.raises(RuntimeError, match="TRADIX_MAX_UPLOAD_BYTES"):
        Settings.from_env()

def test_create_app_rejects_github_limit_above_adapter_cap(tmp_path):
    from tools.artifact_gateway.github_storage import MAX_GITHUB_UPLOAD_BYTES

    settings = Settings(
        project_id="nexora",
        api_key=API_KEY,
        root=tmp_path.resolve(),
        max_upload_bytes=MAX_GITHUB_UPLOAD_BYTES + 1,
        storage_backend="github",
        github_repository="grinlife4-stack/NEXORA",
        github_branch="artifact-intake",
        github_path_prefix="incoming-artifacts",
        github_token="ghp_" + "x" * 36,
    )
    with pytest.raises(RuntimeError, match="max_upload_bytes"):
        create_app(settings)


def test_settings_from_env_rejects_github_limit_above_adapter_cap(monkeypatch, tmp_path):
    from tools.artifact_gateway.github_storage import MAX_GITHUB_UPLOAD_BYTES

    monkeypatch.setenv("TRADIX_PROJECT_ID", "tradix-test")
    monkeypatch.setenv("TRADIX_API_KEY", API_KEY)
    monkeypatch.setenv("TRADIX_ARTIFACT_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv("TRADIX_MAX_UPLOAD_BYTES", str(MAX_GITHUB_UPLOAD_BYTES + 1))
    monkeypatch.setenv("TRADIX_STORAGE_BACKEND", "github")
    with pytest.raises(RuntimeError, match="TRADIX_MAX_UPLOAD_BYTES"):
        Settings.from_env()

