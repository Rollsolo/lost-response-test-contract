"""Adapter loading for the lost-response harness.

An adapter is a module in this package defining a class named
`Adapter` (a base.SystemAdapter subclass) whose `name` matches the
module's file stem. The harness config selects it:

    {"adapter": "<module stem>", "adapter_config": {...}}

See base.py for the contract, zambo.py for the reference
implementation, and stub.py for a copyable template.
"""

import importlib

from .base import SystemAdapter

__all__ = ["SystemAdapter", "load_adapter", "normalize_config"]


def load_adapter(name, adapter_config):
    module = importlib.import_module(f".{name}", __package__)
    adapter_cls = getattr(module, "Adapter")
    return adapter_cls(adapter_config or {})


def normalize_config(raw):
    """Accept both config shapes and return a normalized dict:
    {"adapter", "system_name", "a5_delay_hours", "adapter_config"}.

    Current shape: driver keys at the top level and the adapter's own
    keys under "adapter_config". Legacy shape (the original
    config.zambo.json): every key at the top level, no "adapter" key;
    it selects the zambo adapter and every non-driver key is adapter
    configuration.
    """
    raw = dict(raw or {})
    if "adapter_config" in raw or "adapter" in raw:
        adapter_config = dict(raw.get("adapter_config") or {})
        return {
            "adapter": raw.get("adapter", "zambo"),
            "system_name": raw.get("system_name"),
            "a5_delay_hours": raw.get("a5_delay_hours",
                                      adapter_config.get("a5_delay_hours", 24)),
            "adapter_config": adapter_config,
        }
    adapter_config = {k: v for k, v in raw.items()
                      if k not in ("system_name", "a5_delay_hours")}
    return {
        "adapter": "zambo",
        "system_name": raw.get("system_name"),
        "a5_delay_hours": raw.get("a5_delay_hours", 24),
        "adapter_config": adapter_config,
    }
