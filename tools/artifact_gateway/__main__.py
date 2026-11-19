"""Run the local artifact gateway with: python -m tools.artifact_gateway."""
from __future__ import annotations

import os


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Install the gateway extra: pip install -e '.[gateway]'") from exc
    from tools.artifact_gateway.app import create_app

    host = os.environ.get("TRADIX_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(create_app(), host=host, port=port, access_log=False)


if __name__ == "__main__":
    main()
