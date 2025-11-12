# masha_lang/core/plugin_manager.py
import importlib
import json
import os
from typing import Any, Dict, List, Optional
from .events import EventBus

class CapabilityRegistry:
    """
    Central registry for capabilities and symbol providers.
    It stores only metadata and import targets; the plugin modules are
    imported lazily on first use.
    """
    def __init__(self):
        self.parsers_by_ext: Dict[str, Dict] = {}
        self.symbol_providers: Dict[str, Dict] = {}
        self.executors_by_kind: Dict[str, List[Dict]] = {}
        self.loaded_modules: Dict[str, Any] = {}

    def register_parser(self, ext: str, module_path: str, factory_name: str):
        self.parsers_by_ext[ext] = {"module": module_path, "factory": factory_name}

    def register_symbol(self, symbol_name: str, module_path: str, factory_name: str):
        self.symbol_providers[symbol_name] = {"module": module_path, "factory": factory_name}

    def register_executor(self, ast_kind: str, module_path: str, factory_name: str):
        self.executors_by_kind.setdefault(ast_kind, []).append(
            {"module": module_path, "factory": factory_name}
        )

    def _import_factory(self, module_path: str, factory_name: str):
        if module_path not in self.loaded_modules:
            self.loaded_modules[module_path] = importlib.import_module(module_path)
        mod = self.loaded_modules[module_path]
        return getattr(mod, factory_name)

class PluginManager:
    """
    The only "built-in". Loads config, registers plugin metadata, and resolves
    capabilities lazily when events request them.
    """
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.event_bus = EventBus()
        self.registry = CapabilityRegistry()
        self.config: Dict[str, Any] = {}

    def load_config(self):
        cfg_path = os.path.join(self.root_dir, ".masha", "config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def register_from_config(self):
        # Register parsers by file extension
        for ext, info in self.config.get("parsers", {}).items():
            self.registry.register_parser(ext, info["module"], info["factory"])

        # Register symbol providers (namespaces like 'print')
        for sym, info in self.config.get("symbols", {}).items():
            self.registry.register_symbol(sym, info["module"], info["factory"])

        # Register executors for AST node kinds
        for kind, providers in self.config.get("executors", {}).items():
            for info in providers:
                self.registry.register_executor(kind, info["module"], info["factory"])

        # Optional: allow plugins to attach to events at import time (lazy)
        # The config can list "boot" plugins to bind event handlers
        for boot in self.config.get("boot", []):
            module = importlib.import_module(boot["module"])
            getattr(module, boot["init_fn"])(self)

    # Lazy resolution APIs used by the runner:

    def get_parser_for_extension(self, ext: str):
        meta = self.registry.parsers_by_ext.get(ext)
        if not meta:
            return None
        factory = self.registry._import_factory(meta["module"], meta["factory"])
        return factory(self)  # pass manager for context

    def resolve_symbol(self, symbol_name: str):
        meta = self.registry.symbol_providers.get(symbol_name)
        if not meta:
            return None
        factory = self.registry._import_factory(meta["module"], meta["factory"])
        return factory(self)

    def get_executors_for_kind(self, kind: str):
        metas = self.registry.executors_by_kind.get(kind, [])
        executors = []
        for meta in metas:
            factory = self.registry._import_factory(meta["module"], meta["factory"])
            executors.append(factory(self))
        return executors
