"""Standalone OBIS reference implementation.

This package intentionally has no dependency on TRADIX or BRIDEX runtime code.
"""

__version__ = "0.1.0"

from .peer import ALPN_PROTOCOL, TLS_PROFILE_ID, Credential, OBISClient, OBISPeer, OBISRequestError, OBISServer
from .ecoscan_inventory import register_ecoscan_inventory_capability

__all__ = [
    "ALPN_PROTOCOL",
    "TLS_PROFILE_ID",
    "Credential",
    "OBISClient",
    "OBISPeer",
    "OBISRequestError",
    "OBISServer",
    "register_ecoscan_inventory_capability",
]
