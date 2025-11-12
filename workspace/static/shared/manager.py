import importlib.util
import os
from typing import Any, Dict, List

class ParsieRegistry:
    def __init__(self):
        self.parsers_by_ext: Dict[str, Dict] = {}
        self.symbol_providers: Dict[str, Dict] = {}
        self.executors_by_kind: Dict[str, List[Dict]] = {}
        self.loaded_modules: Dict[str, Any] = {}

    def register_parser(self, ext: str, module_path: str, factory_name: str):
        self.parsers_by_ext[ext] = {"module": module_path, "factory": factory_name}

    def register_symbol(self, symbol_name: str, module_path: str, factory_name: str):
        self.symbol_providers[symbol_name] = {"module": module_path, "factory": factory_name}

    def register_executor(self, kind: str, module_path: str, factory_name: str):
        self.executors_by_kind.setdefault(kind, []).append(
            {"module": module_path, "factory": factory_name}
        )

    def _import_factory(self, module_path: str, factory_name: str):
        # module_path is a logical key we assign (e.g., file path)
        mod = self.loaded_modules.get(module_path)
        if mod is None:
            raise RuntimeError(f"Module not imported for factory lookup: {module_path}")
        return getattr(mod, factory_name)

class ParsiePluginManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.registry = ParsieRegistry()
        self._discovered_files: List[str] = []
        self._imported: Dict[str, bool] = {}

        if os.path.isdir(base_dir):
            for root, _, files in os.walk(base_dir):
                for fn in files:
                    if fn.endswith(".py") and not fn.startswith("_"):
                        self._discovered_files.append(os.path.join(root, fn))

    def _module_key(self, path: str):
        return os.path.relpath(path, self.base_dir).replace("\\", "/")

    def _import(self, path: str):
        if self._imported.get(path):
            return
        mod_key = self._module_key(path)
        spec = importlib.util.spec_from_file_location(mod_key, path)
        if not spec or not spec.loader:
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.registry.loaded_modules[mod_key] = mod
        self._imported[path] = True

        register = getattr(mod, "register", None)
        if callable(register):
            register(self, module_key=mod_key)

    def _ensure_parser_for_ext(self, ext: str):
        if ext in self.registry.parsers_by_ext:
            return
        for path in self._discovered_files:
            if not self._imported.get(path):
                self._import(path)
                if ext in self.registry.parsers_by_ext:
                    return

    def _ensure_executor_for_kind(self, kind: str):
        if kind in self.registry.executors_by_kind:
            return
        for path in self._discovered_files:
            if not self._imported.get(path):
                self._import(path)
                if kind in self.registry.executors_by_kind:
                    return

    def get_parser_for_ext(self, ext: str):
        self._ensure_parser_for_ext(ext)
        meta = self.registry.parsers_by_ext.get(ext)
        if not meta:
            return None
        mod = self.registry.loaded_modules[meta["module"]]
        factory = getattr(mod, meta["factory"])
        return factory(self)

    def get_executors_for_kind(self, kind: str):
        self._ensure_executor_for_kind(kind)
        metas = self.registry.executors_by_kind.get(kind, [])
        result = []
        for meta in metas:
            mod = self.registry.loaded_modules[meta["module"]]
            factory = getattr(mod, meta["factory"])
            result.append(factory(self))
        return result
