"""Independent BRIDEX engineering-plane tools."""

__version__ = "0.1.0"

from .manifest import BridgeManifestError, load_manifest, validate_manifest_data
from .package import build_package, verify_package
from .scaffold import create_bridge_project

__all__ = [
    "BridgeManifestError",
    "build_package",
    "create_bridge_project",
    "load_manifest",
    "validate_manifest_data",
    "verify_package",
]
