# # masha_lang/plugins/print_builtin.py
# from src.core.types import ASTNode

# class PrintSymbolProvider:
#     def __init__(self, pm):
#         self.pm = pm

#     def tokens_to_ast(self, tokens):
#         # Example syntax: print "hello world"
#         # Very naive: treat everything after 'print' as the payload, join with spaces.
#         # A different plugin could provide proper lexing with quotes.
#         payload = " ".join(tokens[1:])
#         # Strip surrounding quotes if present
#         if payload.startswith('"') and payload.endswith('"') and len(payload) >= 2:
#             payload = payload[1:-1]
#         return ASTNode(kind="PrintStatement", data={"text": payload})

# class PrintExecutor:
#     def __init__(self, pm):
#         self.pm = pm

#     def can_handle(self, node: ASTNode) -> bool:
#         return node.kind == "PrintStatement"

#     def execute(self, node: ASTNode):
#         # This is not "built in" to the language; it's plugin-provided behavior
#         print(node.data.get("text", ""))

# def create_symbol_provider(pm):
#     return PrintSymbolProvider(pm)

# def create_executor(pm):
#     return PrintExecutor(pm)

# def register(pm, module_key: str):
#     pm.registry.register_executor(ast_kind="PrintStatement", module_path=module_key, factory_name=create_executor)
#     pm.registry.register_symbol(symbol_name="print", module_path=module_key, factory_name=create_symbol_provider)
# DAMMNIT, who commented this out?
# it was me!
# whoooo are you?
from src.core.types import ASTNode

class PrintSymbolProvider:
    def __init__(self, pm):
        self.pm = pm

    def tokens_to_ast(self, tokens):
        # Example syntax: print "hello world"
        payload = " ".join(tokens[1:])
        # Strip surrounding quotes if present
        if len(payload) >= 2 and payload.startswith('"') and payload.endswith('"'):
            payload = payload[1:-1]
        return ASTNode(kind="PrintStatement", data={"text": payload})

class PrintExecutor:
    def __init__(self, pm):
        self.pm = pm

    def can_handle(self, node: ASTNode) -> bool:
        return node.kind == "PrintStatement"

    def execute(self, node: ASTNode):
        # Plugin-provided behavior
        print(node.data.get("text", ""))

def create_symbol_provider(pm):
    return PrintSymbolProvider(pm)

def create_executor(pm):
    return PrintExecutor(pm)

def register(pm, module_key: str):
    # NOTE: factory_name must be the name of the factory function as a string
    pm.registry.register_executor(kind="PrintStatement", module_path=module_key, factory_name="create_executor")
    pm.registry.register_symbol(symbol_name="print", module_path=module_key, factory_name="create_symbol_provider")
