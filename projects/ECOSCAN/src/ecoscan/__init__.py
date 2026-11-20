"""Independent ECOSCAN core; no TRADIX runtime dependency."""

from .contracts import Adapter, AdapterContractError, AdapterResult, AuthorizationRevoked, BudgetExceeded, BudgetGuard, ScanContext
from .controls import ControlState, ExecutionGate
from .registry import RegistryError, load_registry, parse_registry
from .runner import ScanError, ScanOutcome, ScanRunner
from .store import ProjectStore, StoreError

__all__ = [
    "Adapter",
    "AdapterContractError",
    "AuthorizationRevoked",
    "AdapterResult",
    "BudgetExceeded",
    "BudgetGuard",
    "ControlState",
    "ExecutionGate",
    "ProjectStore",
    "RegistryError",
    "ScanContext",
    "ScanError",
    "ScanOutcome",
    "ScanRunner",
    "StoreError",
    "load_registry",
    "parse_registry",
]

__version__ = "0.1.0"
