from src.core.types import ASTNode
from src.core.plugins_manager import PluginError
import os
import time


class ImportSymbolProvider:
    def __init__(self, pm):
        self.pm = pm

    def tokens_to_ast(self, tokens):
        if not tokens:
            payload = ""
        else:
            payload = " ".join(tokens)
            if len(payload) >= 2 and payload.startswith('[') and payload.endswith(']'):
                payload = payload[1:-1]
        return ASTNode(kind="import", data={"module": payload})



class ImportExecutor:
    def __init__(self, pm):
        self.pm = pm

        # Cache structure (lazy + hot-loading)
        # {
        #   abs_path: {
        #       "ast": [...],
        #       "mtime": float,
        #       "content": str
        #   }
        # }
        self.cache = {}

    def can_handle(self, node: ASTNode) -> bool:
        return node.kind == "import"

    def _resolve_path(self, module):
        # normalize .nakurility path
        rel_path = module
        if not (rel_path.startswith("./") or rel_path.startswith("static/")):
            rel_path = f"static/{rel_path}"
        return self.pm._abs(rel_path)

    def _load_and_parse(self, abs_path, module_name):
        """Perform actual file read + parse (hot reload uses this)"""

        # --- events: before load ---
        self.pm.event_bus.emit(
            "import:file.before_load",
            path=abs_path,
            module_name=module_name
        )

        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        from src.core.types import SourceFile
        sf = SourceFile(path=abs_path, content=content)

        parsed_nodes = self.pm.parser.parse(sf)

        # --- events: after load ---
        self.pm.event_bus.emit(
            "import:file.after_load",
            path=abs_path,
            module_name=module_name,
            ast=parsed_nodes
        )

        return content, parsed_nodes

    def _lazy_load(self, abs_path, module_name):
        """Return AST but perform lazy load + detect hot reload"""

        stat = os.stat(abs_path)
        mtime = stat.st_mtime

        if abs_path not in self.cache:
            # First-time lazy load
            content, parsed = self._load_and_parse(abs_path, module_name)
            self.cache[abs_path] = {
                "mtime": mtime,
                "ast": parsed,
                "content": content,
            }
            return parsed

        # Cached entry exists — check if file changed
        cached = self.cache[abs_path]

        if cached["mtime"] != mtime:
            # HOT RELOAD
            content, parsed = self._load_and_parse(abs_path, module_name)
            cached["mtime"] = mtime
            cached["ast"] = parsed
            cached["content"] = content
            return parsed

        # No changes → return existing AST
        return cached["ast"]


    def execute(self, node: ASTNode):
        module = node.data.get("module", "").strip()

        # Normal plugin import
        if not module.endswith(".nakurility"):
            return module   # unchanged behavior

        # Resolve & validate
        abs_path = self._resolve_path(module)

        if not os.path.isfile(abs_path):
            raise PluginError(f".nakurility file not found: {abs_path}")

        # LAZY + HOT load here
        return self._lazy_load(abs_path, module)



def create_symbol_provider(pm):
    return ImportSymbolProvider(pm)

def create_executor(pm):
    return ImportExecutor(pm)

def register(pm, module_key: str):
    pm.registry.register_executor(
        kind="import",
        module_path=module_key,
        factory_name="create_executor"
    )
    pm.registry.register_symbol(
        symbol_name="import",
        module_path=module_key,
        factory_name="create_symbol_provider"
    )
