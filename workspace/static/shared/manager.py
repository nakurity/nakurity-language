import importlib.util
import os
from typing import Any, Dict, List, Optional


class ParsieRegistry:
    """Runtime registry (only contains what was ACTUALLY loaded)."""

    def __init__(self):
        self.parsers_by_ext: Dict[str, Dict] = {}
        self.symbol_providers: Dict[str, Dict] = {}
        self.executors_by_kind: Dict[str, List[Dict]] = {}
        self.loaded_modules: Dict[str, Any] = {}

    def register_parser(self, ext: str, module_path: str, factory_name: str):
        """Register a parser for a file extension."""
        self.parsers_by_ext[ext] = {
            "module": module_path,
            "factory": factory_name
        }

    def register_symbol(self, symbol_name: str, module_path: str, factory_name: str):
        """Register a symbol provider."""
        self.symbol_providers[symbol_name] = {
            "module": module_path,
            "factory": factory_name
        }

    def register_executor(self, kind: str, module_path: str, factory_name: str):
        """Register an executor for a specific node kind."""
        if kind not in self.executors_by_kind:
            self.executors_by_kind[kind] = []
        
        self.executors_by_kind[kind].append({
            "module": module_path,
            "factory": factory_name
        })

class ParsiePluginManager:
    """
    True lazy plugin manager:
    - No directory scanning.
    - No loading until requested.
    - Plugins self-register when imported.
    """

    def __init__(self):
        self.registry = ParsieRegistry()

        # Known plugin files: { "print": "/abs/path/print.py" }
        self.known_plugin_files: Dict[str, str] = {}

        # To avoid re-importing
        self._imported_cache: Dict[str, bool] = {}

    # ---------------------------------------------------------
    # REGISTRATION OF POSSIBLE FILES (lazy sources)
    # ---------------------------------------------------------

    def register_plugin_file(self, symbol_name: str, file_path: str):
        """Declare where a plugin for 'symbol_name' *might* live."""
        self.known_plugin_files[symbol_name] = os.path.abspath(file_path)

    # ---------------------------------------------------------
    # INTERNAL IMPORT
    # ---------------------------------------------------------

    def _import_file(self, file_path: str):
        """Import file only once, triggering plugin registration."""

        file_path = os.path.abspath(file_path)

        if self._imported_cache.get(file_path):
            return

        spec = importlib.util.spec_from_file_location(file_path, file_path)
        if not spec or not spec.loader:
            return

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Save module
        self.registry.loaded_modules[file_path] = mod
        self._imported_cache[file_path] = True

        # Call its register() if exists
        register_fn = getattr(mod, "register", None)
        if callable(register_fn):
            register_fn(self, module_key=file_path)

    # ---------------------------------------------------------
    # PUBLIC GETTERS — ALL LAZY
    # ---------------------------------------------------------

    # PARSER
    def get_parser_for_ext(self, ext: str):
        meta = self.registry.parsers_by_ext.get(ext)
        if not meta:
            # Try importing plugin with same key name
            plugin_key = ext.lstrip(".")
            fp = self.known_plugin_files.get(plugin_key)
            if fp:
                self._import_file(fp)

        meta = self.registry.parsers_by_ext.get(ext)
        if not meta:
            return None

        mod = self.registry.loaded_modules[meta["module"]]
        factory = getattr(mod, meta["factory"])
        return factory(self)

    # SYMBOL PROVIDER
    def get_symbol_provider(self, symbol_name: str):
        meta = self.registry.symbol_providers.get(symbol_name)
        if not meta:
            fp = self.known_plugin_files.get(symbol_name)
            if fp:
                self._import_file(fp)

        meta = self.registry.symbol_providers.get(symbol_name)
        if not meta:
            return None

        mod = self.registry.loaded_modules[meta["module"]]
        return getattr(mod, meta["factory"])(self)

    # EXECUTORS
    def get_executors_for_kind(self, kind: str):
        metas = self.registry.executors_by_kind.get(kind)
        if not metas:
            fp = self.known_plugin_files.get(kind)
            if fp:
                self._import_file(fp)

        metas = self.registry.executors_by_kind.get(kind, [])
        out = []
        for meta in metas:
            mod = self.registry.loaded_modules[meta["module"]]
            out.append(getattr(mod, meta["factory"])(self))
        return out
