"""Standalone OBIS reference implementation.

This package intentionally has no dependency on TRADIX or BRIDEX runtime code.
"""

__version__ = "0.1.0"

from .peer import Credential, OBISClient, OBISPeer, OBISRequestError, OBISServer, create_tls13_client_context, create_tls13_server_context
from .ecoscan_inventory import register_ecoscan_inventory_capability

__all__ = [
    "Credential",
    "OBISClient",
    "OBISPeer",
    "OBISRequestError",
    "OBISServer",
    "create_tls13_client_context",
    "create_tls13_server_context",
    "register_ecoscan_inventory_capability",
]
