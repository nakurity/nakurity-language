# src/core/plugin_manager.py
import importlib.util
import json
import os
import sys
from typing import Any, Dict, List, Optional
from .events import EventBus

class CapabilityRegistry:
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
        # module_path is a logical key we assign (e.g., file path)
        mod = self.loaded_modules.get(module_path)
        if mod is None:
            # This should not happen if registration only occurs post-import
            raise RuntimeError(f"Module not imported for factory lookup: {module_path}")
        return getattr(mod, factory_name)

class PluginManager:
    """
    Core: config, event bus, lazy .py plugin import, capability resolution.
    """
    def __init__(self, root_dir: str, bare: bool = False):
        self.root_dir = root_dir
        self.event_bus = EventBus()
        self.registry = CapabilityRegistry()
        self.config: Dict[str, Any] = {}

        self.plugins_dir: Optional[str] = None
        self.modules_dir: Optional[str] = None
        self.needy_plugins_dir: Optional[str] = None
        self.enable_needy = not bare

        # Internal tracking
        self._discovered_plugin_files: List[str] = []
        self._imported_plugin_files: Dict[str, bool] = {}

        if os.path.isdir(self.reverie_dir):
            self.autorunfiles = self.findpyfiles(self.reveriedir)
        else:
            self.autorunfiles = []

    def run_autorun(self):
        for path in self.autorunfiles:
            self.importand_register(path)
            modkey = self.modulekeyfor_file(path)
            mod = self.registry.loadedmodules.get(modkey)
            if mod and hasattr(mod, "autorun"):
                try:
                    mod.autorun(self)
                except Exception as e:
                    print(f"[autorun error] {path}: {e}")

    def _abs(self, rel: str) -> str:
        return os.path.join(self.root_dir, rel)

    def load_config(self):
        cfg_path = self._abs("static/.masha/config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        paths = self.config.get("paths", {})
        self.plugins_dir = self._abs(paths.get("plugins_dir", "static/.masha/plugins"))
        self.modules_dir = self._abs(paths.get("modules_dir", "static/.parsie/modules"))
        self.needy_plugins_dir = self._abs(paths.get("needy_plugins_dir", "static/.needy/plugins"))

        needy_cfg = self.config.get("needy", {})
        auto_enable = bool(needy_cfg.get("auto_enable", True))
        self.enable_needy = auto_enable and self.enable_needy

        # sys.path: allow shared modules under static/.parsie/modules
        if self.modules_dir and os.path.isdir(self.modules_dir) and self.modules_dir not in sys.path:
            sys.path.append(self.modules_dir)

        # Discover plugin files up-front (without importing)
        if self.plugins_dir and os.path.isdir(self.plugins_dir):
            self._discovered_plugin_files += self._find_py_files(self.plugins_dir)

        # Needy plugins auto-load unless :bare
        if self.enable_needy and self.needy_plugins_dir and os.path.isdir(self.needy_plugins_dir):
            needy_files = self._find_py_files(self.needy_plugins_dir)
            for path in needy_files:
                self._import_and_register(path)

    def _find_py_files(self, base_dir: str) -> List[str]:
        py_files = []
        for root, _, files in os.walk(base_dir):
            for fn in files:
                if fn.endswith(".py") and not fn.startswith("_"):
                    py_files.append(os.path.join(root, fn))
        return py_files

    def _module_key_for_file(self, file_path: str) -> str:
        # Use a stable key for registry.loaded_modules and factory lookup
        return os.path.relpath(file_path, self.root_dir).replace("\\", "/")

    def _import_and_register(self, file_path: str):
        if self._imported_plugin_files.get(file_path):
            return  # already imported
        mod_key = self._module_key_for_file(file_path)

        spec = importlib.util.spec_from_file_location(mod_key, file_path)
        if spec is None or spec.loader is None:
            return
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            # If a plugin fails to import, skip it quietly
            return

        # Store module for factory lookups
        self.registry.loaded_modules[mod_key] = mod
        self._imported_plugin_files[file_path] = True

        # Require a register(pm) function
        register_fn = getattr(mod, "register", None)
        if callable(register_fn):
            # The plugin calls pm.registry.register_xxx(...)
            register_fn(self, module_key=mod_key)
        # If there's no register, treat as non-plugin

    # Lazy resolution: import plugins only when needed

    def _ensure_parsers_loaded_for_ext(self, ext: str):
        if ext in self.registry.parsers_by_ext:
            return
        # Try all not-yet-imported plugins
        for path in list(self._discovered_plugin_files):
            if not self._imported_plugin_files.get(path):
                self._import_and_register(path)
                # Early exit if parser got registered
                if ext in self.registry.parsers_by_ext:
                    return

    def _ensure_symbol_loaded(self, name: str):
        if name in self.registry.symbol_providers:
            return
        for path in list(self._discovered_plugin_files):
            if not self._imported_plugin_files.get(path):
                self._import_and_register(path)
                if name in self.registry.symbol_providers:
                    return

    def _ensure_executors_loaded_for_kind(self, kind: str):
        if kind in self.registry.executors_by_kind and self.registry.executors_by_kind[kind]:
            return
        for path in list(self._discovered_plugin_files):
            if not self._imported_plugin_files.get(path):
                self._import_and_register(path)
                if kind in self.registry.executors_by_kind and self.registry.executors_by_kind[kind]:
                    return

    # Public APIs used by the runner:

    def get_parser_for_extension(self, ext: str):
        self._ensure_parsers_loaded_for_ext(ext)
        meta = self.registry.parsers_by_ext.get(ext)
        if not meta:
            return None
        factory = self.registry._import_factory(meta["module"], meta["factory"])
        return factory(self)

    def resolve_symbol(self, symbol_name: str):
        self._ensure_symbol_loaded(symbol_name)
        meta = self.registry.symbol_providers.get(symbol_name)
        if not meta:
            return None
        factory = self.registry._import_factory(meta["module"], meta["factory"])
        return factory(self)

    def get_executors_for_kind(self, kind: str):
        self._ensure_executors_loaded_for_kind(kind)
        metas = self.registry.executors_by_kind.get(kind, [])
        executors = []
        for meta in metas:
            factory = self.registry._import_factory(meta["module"], meta["factory"])
            executors.append(factory(self))
        return executors
