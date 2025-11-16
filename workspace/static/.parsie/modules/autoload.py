# static/.parsie/modules/autoload.py

from src.core.types import ASTNode

class AutoloadSymbolProvider:
    def __init__(self, pm):
        self.pm = pm  # This is ParsiePluginManager

    def tokens_to_ast(self, tokens):
        """
        Syntax:
            autoload [PluginName]
        """
        if len(tokens) < 2:
            return ASTNode(kind="autoload", data={
                "error": "missing plugin name",
                "raw": " ".join(tokens)
            })

        raw = tokens[1].strip()

        # Expect format: [Outerlands]
        if raw.startswith("[") and raw.endswith("]"):
            plugin_name = raw[1:-1]
        else:
            plugin_name = raw

        return ASTNode(kind="autoload", data={"plugin": plugin_name})


class AutoloadExecutor:
    def __init__(self, pm):
        self.pm = pm  # This is ParsiePluginManager

    def can_handle(self, node):
        return node.kind == "autoload"

    def execute(self, node):
        plugin = node.data.get("plugin")

        # The plugin file path for Parsie
        file_path = f"static/.parsie/modules/{plugin.lower()}.py"

        try:
            # Force import early
            self.pm._import_file(self.pm.pm._abs(file_path))
        except Exception as e:
            print(f"[autoload] failed to load '{plugin}': {e}")


def create_symbol_provider(pm):
    return AutoloadSymbolProvider(pm)

def create_executor(pm):
    return AutoloadExecutor(pm)

def register(pm, module_key):
    pm.registry.register_symbol(
        symbol_name="autoload",
        module_path=module_key,
        factory_name="create_symbol_provider"
    )

    pm.registry.register_executor(
        kind="autoload",
        module_path=module_key,
        factory_name="create_executor"
    )
