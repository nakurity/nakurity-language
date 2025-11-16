# static/.parsie/modules/comment.py

# Since the parser loads modules via name resolution from a head.
# this comment module needs to be ran with a syntax like: comment "text text text"

from src.core.types import ASTNode

class CommentSymbolProvider:
    def __init__(self, pm):
        self.pm = pm

    def tokens_to_ast(self, tokens):
        # Example syntax: print "hello world"
        payload = " ".join(tokens[1:])
        # Strip surrounding quotes if present
        if len(payload) >= 2 and payload.startswith('"') and payload.endswith('"'):
            payload = payload[1:-1]

        # TODO: add comment tracing

        # We have to import this with import xD
        # import [Commenting]
        return ASTNode(kind="Commenting", data={"text": payload})

class CommentExecutor:
    def __init__(self, pm):
        self.pm = pm

    def can_handle(self, node: ASTNode) -> bool:
        return node.kind == "Commenting"

    def execute(self, node: ASTNode):
        # hmmm, what should we do here?
        pass

def create_symbol_provider(pm):
    return CommentSymbolProvider(pm)

def create_executor(pm):
    return CommentExecutor(pm)

def register(pm, module_key: str):
    # NOTE: factory_name must be the name of the factory function as a string
    pm.registry.register_executor(kind="Commenting", module_path=module_key, factory_name="create_executor")
    pm.registry.register_symbol(symbol_name="comment", module_path=module_key, factory_name="create_symbol_provider")
