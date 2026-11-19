"""Authenticated, project-scoped artifact upload gateway.

Deploy one instance per project with project-specific credentials and storage.
The gateway never chooses a project namespace from an untrusted upload field.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from tools.artifact_intake.artifact_intake import ArtifactError, inspect_zip
from tools.artifact_intake.document_readers import DocumentReadError, read_document

PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
ARTIFACT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class Settings:
    project_id: str
    api_key: str
    root: Path
    max_upload_bytes: int = 50 * 1024 * 1024
    storage_backend: str = "local"
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        project_id = os.environ.get("TRADIX_PROJECT_ID", "")
        api_key = os.environ.get("TRADIX_API_KEY", "")
        root_raw = os.environ.get("TRADIX_ARTIFACT_ROOT", "")
        if not PROJECT_RE.fullmatch(project_id):
            raise RuntimeError("TRADIX_PROJECT_ID must be a lowercase project slug")
        if len(api_key) < 32:
            raise RuntimeError("TRADIX_API_KEY must contain at least 32 characters")
        if not root_raw or not Path(root_raw).is_absolute():
            raise RuntimeError("TRADIX_ARTIFACT_ROOT must be an absolute persistent path")
        backend = os.environ.get("TRADIX_STORAGE_BACKEND", "local").lower()
        if backend not in {"local", "s3"}:
            raise RuntimeError("TRADIX_STORAGE_BACKEND must be 'local' or 's3'")
        values = {
            "s3_endpoint_url": os.environ.get("TRADIX_S3_ENDPOINT_URL"),
            "s3_region": os.environ.get("TRADIX_S3_REGION"),
            "s3_bucket": os.environ.get("TRADIX_S3_BUCKET"),
            "s3_access_key_id": os.environ.get("TRADIX_S3_ACCESS_KEY_ID"),
            "s3_secret_access_key": os.environ.get("TRADIX_S3_SECRET_ACCESS_KEY"),
        }
        if backend == "s3" and not all(values.values()):
            raise RuntimeError("S3 backend requires endpoint, region, bucket and credentials")
        return cls(project_id=project_id, api_key=api_key, root=Path(root_raw),
                   storage_backend=backend, **values)


def _safe_filename(name: str | None) -> str:
    raw = (name or "upload.bin").replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "._-")[:120]
    return cleaned or "upload.bin"


def _extract(path: Path, filename: str) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".zip":
        report = inspect_zip(path)
        return {
            "kind": "zip",
            "valid": True,
            "entry_count": report["entry_count"],
            "uncompressed_bytes": report["uncompressed_bytes"],
            "entries": report["entries"],
        }
    if suffix in {".pdf", ".docx", ".xlsx"}:
        return read_document(path)
    if suffix in {".txt", ".md", ".json", ".csv", ".xml", ".yaml", ".yml", ".py", ".js", ".ts", ".html", ".css"}:
        raw = path.read_bytes()
        if len(raw) > 2_000_000:
            raise ArtifactError("text extraction limited to 2 MB")
        try:
            return {"kind": "text", "encoding": "utf-8", "text": raw.decode("utf-8")}
        except UnicodeDecodeError:
            return {"kind": "binary", "reason": "file is not valid UTF-8"}
    return {"kind": "binary", "reason": "no registered reader for this file type"}


def _s3_client(settings: Settings):
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("S3 backend requires the 'storage' extra") from exc
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    if not PROJECT_RE.fullmatch(config.project_id):
        raise RuntimeError("invalid project namespace")
    if len(config.api_key) < 32:
        raise RuntimeError("API key must contain at least 32 characters")
    if not config.root.is_absolute():
        raise RuntimeError("artifact root must be an absolute path")
    if config.max_upload_bytes < 1:
        raise RuntimeError("max upload size must be positive")
    if config.storage_backend not in {"local", "s3"}:
        raise RuntimeError("unsupported storage backend")
    if config.storage_backend == "s3" and not all((
        config.s3_endpoint_url, config.s3_region, config.s3_bucket,
        config.s3_access_key_id, config.s3_secret_access_key
    )):
        raise RuntimeError("S3 backend is missing required configuration")

    app = FastAPI(
        title="TRADIX Artifact Gateway",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    project_root = (config.root / config.project_id).resolve()
    objects_dir = project_root / "objects"
    receipts_dir = project_root / "receipts"
    temp_dir = project_root / "tmp"
    for directory in (objects_dir, receipts_dir, temp_dir):
        directory.mkdir(parents=True, exist_ok=True)
        if project_root not in directory.resolve().parents:
            raise RuntimeError("artifact directory escaped configured project root")

    def authenticate(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
        supplied = authorization[7:]
        if not hmac.compare_digest(supplied, config.api_key):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "tradix-artifact-gateway"}

    @app.post("/v1/artifacts", dependencies=[Depends(authenticate)])
    async def upload_artifact(
        file: UploadFile = File(...),
        expected_sha256: str | None = Header(default=None, alias="X-Content-SHA256"),
    ):
        filename = _safe_filename(file.filename)
        if expected_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            raise HTTPException(status_code=400, detail="invalid X-Content-SHA256 header")
        digest = hashlib.sha256()
        size = 0
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=temp_dir, prefix="incoming-", delete=False
            ) as output:
                temp_path = Path(output.name)
                while chunk := await file.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > config.max_upload_bytes:
                        raise HTTPException(status_code=413, detail="upload exceeds configured size limit")
                    digest.update(chunk)
                    output.write(chunk)
            sha256 = digest.hexdigest()
            if expected_sha256 and not hmac.compare_digest(sha256, expected_sha256.lower()):
                raise HTTPException(status_code=422, detail="SHA-256 mismatch")
            try:
                extraction = _extract(temp_path, filename)
            except (ArtifactError, DocumentReadError) as exc:
                raise HTTPException(status_code=422, detail=f"artifact validation failed: {exc}") from exc

            artifact_id = uuid.uuid4().hex
            object_key = f"projects/{config.project_id}/objects/{sha256[:2]}/{sha256}"
            if config.storage_backend == "local":
                object_path = objects_dir / sha256[:2] / sha256
                object_path.parent.mkdir(parents=True, exist_ok=True)
                if object_path.exists():
                    if object_path.stat().st_size != size:
                        raise HTTPException(status_code=409, detail="existing content hash has inconsistent size")
                    temp_path.unlink(missing_ok=True)
                    temp_path = None
                else:
                    os.replace(temp_path, object_path)
                    temp_path = None
                storage_ref = str(object_path.relative_to(project_root))
            else:
                client = _s3_client(config)
                with temp_path.open("rb") as source:
                    client.put_object(
                        Bucket=config.s3_bucket,
                        Key=object_key,
                        Body=source,
                        ContentLength=size,
                        Metadata={"sha256": sha256, "project-id": config.project_id},
                    )
                head = client.head_object(Bucket=config.s3_bucket, Key=object_key)
                if head.get("ContentLength") != size or head.get("Metadata", {}).get("sha256") != sha256:
                    raise HTTPException(status_code=502, detail="remote storage verification failed")
                storage_ref = f"s3://{config.s3_bucket}/{object_key}"

            receipt = {
                "artifact_id": artifact_id,
                "project_id": config.project_id,
                "filename": filename,
                "size_bytes": size,
                "sha256": sha256,
                "storage_backend": config.storage_backend,
                "storage_ref": storage_ref,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "extraction": extraction,
            }
            receipt_path = receipts_dir / f"{artifact_id}.json"
            temporary_receipt = receipt_path.with_suffix(".json.tmp")
            temporary_receipt.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(temporary_receipt, receipt_path)
            return JSONResponse(status_code=201, content=receipt)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            await file.close()

    @app.get("/v1/artifacts/{artifact_id}", dependencies=[Depends(authenticate)])
    def get_receipt(artifact_id: str):
        if not ARTIFACT_ID_RE.fullmatch(artifact_id):
            raise HTTPException(status_code=404, detail="artifact not found")
        receipt_path = receipts_dir / f"{artifact_id}.json"
        if not receipt_path.is_file():
            raise HTTPException(status_code=404, detail="artifact not found")
        return json.loads(receipt_path.read_text(encoding="utf-8"))

    return app
