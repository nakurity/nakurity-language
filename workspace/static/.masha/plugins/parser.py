# masha_lang/plugins/parser_simple.py
from typing import List
from core.types import ASTNode, SourceFile

def attach_events(pm):
    # If you want event-driven parsing or extra hooks, bind them here.
    # Kept empty for simplicity in this example.
    pass

class SimpleParser:
    """
    Extremely minimal parser:
    - Splits lines into tokens by whitespace.
    - Treats first token as a potential symbol.
    - Delegates interpretation to the symbol provider lazily.
    """
    def __init__(self, pm):
        self.pm = pm

    def tokenize_line(self, line: str) -> List[str]:
        # Still "dumb": no quotes or escapes; plugins can replace this parser entirely
        return line.strip().split()

    def parse(self, source: SourceFile):
        nodes = []
        for line in source.content.splitlines():
            if not line.strip():
                continue
            tokens = self.tokenize_line(line)
            head = tokens[0]

            # Lazy resolve: if there's a symbol provider, let it transform tokens to AST
            sym = self.pm.resolve_symbol(head)
            if sym:
                node = sym.tokens_to_ast(tokens)
                nodes.append(node)
            else:
                # Unknown symbol: emit a generic node to be handled by whoever registers it
                nodes.append(ASTNode(kind="UnknownStatement", data={"tokens": tokens}))
        return nodes
        
def create_parser(pm):
    return _SimpleParser(pm)

def register(pm, module_key: str):
    # Register the parser for .masha extension
    pm.registry.registerparser(ext=".masha", modulepath=modulekey, factoryname="create_parser")
