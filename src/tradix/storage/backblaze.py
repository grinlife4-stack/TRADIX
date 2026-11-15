"""Backblaze B2 adapter using its S3-compatible API.

Credentials are read only from environment variables. Never log or serialize them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class BackblazeConfig:
    endpoint_url: str
    region: str
    bucket_name: str
    application_key_id: str
    application_key: str = field(repr=False)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "BackblazeConfig":
        env = os.environ if environ is None else environ
        names = {
            "endpoint_url": "B2_ENDPOINT",
            "region": "B2_REGION",
            "bucket_name": "B2_BUCKET_NAME",
            "application_key_id": "B2_APPLICATION_KEY_ID",
            "application_key": "B2_APPLICATION_KEY",
        }
        values = {field: env.get(name, "").strip() for field, name in names.items()}
        missing = [names[field] for field, value in values.items() if not value]
        if missing:
            raise ValueError("Missing required Backblaze settings: " + ", ".join(missing))

        parsed = urlparse(values["endpoint_url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/"):
            raise ValueError("B2_ENDPOINT must be an HTTPS endpoint URL without a bucket path")
        expected_host = f"s3.{values['region']}.backblazeb2.com".lower()
        if parsed.hostname.lower() != expected_host:
            raise ValueError("B2_ENDPOINT host must match B2_REGION")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("B2_ENDPOINT must not contain credentials, query parameters, or a fragment")
        if not values["bucket_name"]:
            raise ValueError("B2_BUCKET_NAME cannot be empty")
        return cls(**values)

    def create_client(self):
        """Create an AWS SDK S3 client configured for Backblaze B2."""
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "Backblaze support requires the optional dependency: pip install '.[storage]'"
            ) from exc

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.application_key_id,
            aws_secret_access_key=self.application_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
