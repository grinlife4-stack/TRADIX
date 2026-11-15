"""Verify Backblaze B2 access. Optional --write-test creates a tiny retained object.

Required environment variables:
  B2_ENDPOINT=https://s3.<region>.backblazeb2.com
  B2_REGION=<region>
  B2_BUCKET_NAME=<bucket>
  B2_APPLICATION_KEY_ID=<application key ID>
  B2_APPLICATION_KEY=<application key secret>

The write test deliberately does not delete its object: B2 buckets are versioned
and a normal delete creates a delete marker rather than erasing prior versions.
"""

from __future__ import annotations

import argparse
import sys
import uuid

from tradix.storage.backblaze import BackblazeConfig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-test",
        action="store_true",
        help="upload and read back a tiny object under healthchecks/ (retained in the bucket)",
    )
    args = parser.parse_args()

    try:
        config = BackblazeConfig.from_env()
        client = config.create_client()
        response = client.list_objects_v2(Bucket=config.bucket_name, MaxKeys=1)
        print(f"B2_AUTH_AND_BUCKET_READ=PASS bucket={config.bucket_name}")
        print(f"OBJECTS_VISIBLE_IN_SAMPLE={len(response.get('Contents', []))}")

        if args.write_test:
            key = f"healthchecks/connectivity-{uuid.uuid4().hex}.txt"
            payload = b"TRADIX Backblaze B2 connectivity check v1\n"
            client.put_object(Bucket=config.bucket_name, Key=key, Body=payload)
            result = client.get_object(Bucket=config.bucket_name, Key=key)
            actual = result["Body"].read()
            if actual != payload:
                raise RuntimeError("Uploaded object did not match the downloaded content")
            print(f"B2_WRITE_AND_READBACK=PASS key={key}")
            print("NOTE=The small health-check object is retained because B2 keeps object versions.")
        else:
            print("B2_WRITE_TEST=NOT_RUN (pass --write-test to upload a tiny retained object)")
        return 0
    except Exception as exc:
        # Do not print environment values, request headers, or credential-bearing objects.
        print(f"B2_VERIFICATION=FAIL error_type={type(exc).__name__} message={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
