from src.core.types import ASTNode

class ImportSymbolProvider:
    def __init__(self, pm):
        self.pm = pm

    def tokens_to_ast(self, tokens):
        # Example syntax: import [PrintStatement]
        if not tokens:
            payload = ""
        else:
            # Join all remaining tokens as the payload
            payload = " ".join(tokens)
            # Strip surrounding quotes if present
            if len(payload) >= 2 and payload.startswith('[') and payload.endswith(']'):
                payload = payload[1:-1]
        return ASTNode(kind="import", data={"module": payload})

class ImportExecutor:
    def __init__(self, pm):
        self.pm = pm

    def can_handle(self, node: ASTNode) -> bool:
        return node.kind == "import"

    def execute(self, node: ASTNode):
        # Plugin-provided behavior
        return node.data.get("module")

def create_symbol_provider(pm):
    return ImportSymbolProvider(pm)

def create_executor(pm):
    return ImportExecutor(pm)

def register(pm, module_key: str):
    # NOTE: factory_name must be the name of the factory function as a string
    pm.registry.register_executor(kind="import", module_path=module_key, factory_name="create_executor")
    pm.registry.register_symbol(symbol_name="import", module_path=module_key, factory_name="create_symbol_provider")
