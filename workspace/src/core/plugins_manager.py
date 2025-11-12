# src/core/plugin_manager.py
import importlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from .events import EventBus

class CapabilityRegistry:
    """
    Stores metadata to import factories lazily.
    Filled by scanning plugin manifests on-demand.
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
    The only built-in: config, event bus, lazy manifest scanning, capability resolution.
    """
    def __init__(self, root_dir: str, bare: bool = False):
        self.root_dir = root_dir
        self.event_bus = EventBus()
        self.registry = CapabilityRegistry()
        self.config: Dict[str, Any] = {}
        self.plugins_dirs: List[str] = []
        self.modules_dir: Optional[str] = None
        self.needy_plugins_dir: Optional[str] = None
        self.enable_needy = not bare
        self._scanned_dirs: Dict[str, bool] = {}

    def _abs(self, rel: str) -> str:
        return os.path.join(self.root_dir, rel)

    def load_config(self):
        cfg_path = self._abs("static/.masha/config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        paths = self.config.get("paths", {})
        plugins_dir = self._abs(paths.get("plugins_dir", "static/.masha/plugins"))
        modules_dir = self._abs(paths.get("modules_dir", "static/.parsie/modules"))
        needy_dir  = self._abs(paths.get("needy_plugins_dir", "static/.needy/plugins"))

        self.plugins_dirs = [plugins_dir]
        self.modules_dir = modules_dir if os.path.isdir(modules_dir) else None
        self.needy_plugins_dir = needy_dir if os.path.isdir(needy_dir) else None

        # Honor needy auto_enable unless :bare overrides it
        needy_cfg = self.config.get("needy", {})
        auto_enable = bool(needy_cfg.get("auto_enable", True))
        self.enable_needy = auto_enable and self.enable_needy

        # sys.path augmentation so plugin modules can be imported
        # Add static as a package root if needed
        static_root = self._abs("static")
        for p in [static_root, self.modules_dir]:
            if p and p not in sys.path and os.path.isdir(p):
                sys.path.append(p)

        # Include needy plugins directory in discovery set unless bare
        if self.enable_needy and self.needy_plugins_dir:
            self.plugins_dirs.append(self.needy_plugins_dir)

    def _iter_plugin_manifests(self) -> List[Tuple[str, Dict]]:
        manifests = []
        for base in self.plugins_dirs:
            if not os.path.isdir(base):
                continue
            if self._scanned_dirs.get(base):
                continue
            for entry in os.listdir(base):
                plug_dir = os.path.join(base, entry)
                if not os.path.isdir(plug_dir):
                    continue
                manifest_path = os.path.join(plug_dir, "plugin.json")
                if os.path.isfile(manifest_path):
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            mf = json.load(f)
                        manifests.append((plug_dir, mf))
                    except Exception:
                        # ignore malformed manifest
                        pass
            self._scanned_dirs[base] = True
        return manifests

    def _index_capabilities_for(self, capability: str, key: str):
        """
        capability: 'parser' | 'symbol' | 'executor'
        key: extension for parser, symbol name for symbol, ast kind for executor
        """
        for _, mf in self._iter_plugin_manifests():
            mod = mf.get("module")  # must be importable (e.g., "masha.plugins.print_builtin")
            caps = mf.get("capabilities", {})
            if capability == "parser":
                for item in caps.get("parsers", []):
                    if item.get("ext") == key:
                        self.registry.register_parser(item["ext"], mod, item["factory"])
                        return
            elif capability == "symbol":
                for item in caps.get("symbols", []):
                    if item.get("name") == key:
                        self.registry.register_symbol(item["name"], mod, item["factory"])
                        return
            elif capability == "executor":
                for item in caps.get("executors", []):
                    if item.get("kind") == key:
                        self.registry.register_executor(item["kind"], mod, item["factory"])
                        # do not return; allow multiple executors

    # Lazy resolution APIs

    def get_parser_for_extension(self, ext: str):
        meta = self.registry.parsers_by_ext.get(ext)
        if not meta:
            self._index_capabilities_for("parser", ext)
            meta = self.registry.parsers_by_ext.get(ext)
        if not meta:
            return None
        factory = self.registry._import_factory(meta["module"], meta["factory"])
        return factory(self)

    def resolve_symbol(self, symbol_name: str):
        meta = self.registry.symbol_providers.get(symbol_name)
        if not meta:
            self._index_capabilities_for("symbol", symbol_name)
            meta = self.registry.symbol_providers.get(symbol_name)
        if not meta:
            return None
        factory = self.registry._import_factory(meta["module"], meta["factory"])
        return factory(self)

    def get_executors_for_kind(self, kind: str):
        metas = self.registry.executors_by_kind.get(kind)
        if not metas:
            self._index_capabilities_for("executor", kind)
            metas = self.registry.executors_by_kind.get(kind, [])
        executors = []
        for meta in metas:
            factory = self.registry._import_factory(meta["module"], meta["factory"])
            executors.append(factory(self))
        return executors
