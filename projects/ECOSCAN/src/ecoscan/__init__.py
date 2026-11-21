"""Independent ECOSCAN core; no TRADIX runtime dependency."""

from .contracts import Adapter, AdapterResult, AuthorizationRevoked, BudgetExceeded, BudgetGuard, ScanContext
from .controls import ControlState, ExecutionGate
from .filesystem import FilesystemAdapter
from .registry import EcosystemRegistry, RegistryError, load_registry, parse_registry
from .runner import ScanError, ScanOutcome, ScanRunner
from .store import ProjectStore, StoreError
from .transfer import TransferError, export_store, import_store

__all__ = [
    "Adapter", "AdapterResult", "AuthorizationRevoked", "BudgetExceeded", "BudgetGuard",
    "ControlState", "EcosystemRegistry", "ExecutionGate", "FilesystemAdapter", "ProjectStore",
    "RegistryError", "ScanContext", "ScanError", "ScanOutcome", "ScanRunner", "StoreError",
    "TransferError", "export_store", "import_store", "load_registry", "parse_registry",
]
__version__ = "0.1.0"
