# # masha_lang/plugins/parser_simple.py
from typing import List
from src.core.types import ASTNode, SourceFile

# def attach_events(pm):
#     # If you want event-driven parsing or extra hooks, bind them here.
#     # Kept empty for simplicity in this example.
#     pass

# class SimpleParser:
#     """
#     Extremely minimal parser:
#     - Splits lines into tokens by whitespace.
#     - Treats first token as a potential symbol.
#     - Delegates interpretation to the symbol provider lazily.
#     """
#     def __init__(self, pm):
#         self.pm = pm

#     def tokenize_line(self, line: str) -> List[str]:
#         # Still "dumb": no quotes or escapes; plugins can replace this parser entirely
#         return line.strip().split()

#     def parse(self, source: SourceFile):
#         nodes = []
#         for line in source.content.splitlines():
#             if not line.strip():
#                 continue
#             tokens = self.tokenize_line(line)
#             head = tokens[0]

#             # kindly, good sir!
#             def lazy_resolve(we_will_kindly_ask_for_the_statement: str):
#                 # Lazy resolve: if there's a symbol provider, let it transform tokens to AST
#                 sym = self.pm.resolve_symbol(head)
#                 if sym:
#                     node = sym.tokens_to_ast(tokens)
#                     nodes.append(node)
#                     return "we found... a printer...?"
#                 else:
#                     # should probably check if the string is empty
#                     # but its impossible to be empty when this condition is met, right...?
#                     self.pm._ensure_symbol_loaded(head)
#                     self.pm._ensure_executors_loaded_for_kind(we_will_kindly_ask_for_the_statement)
#                     lazy_resolve("") # it should already be loaded, unless....

#             if (line.startswith("import: ")):
#                 we_killed_its_head_silly = line.replace("import: ", "", 1)
#                 lazy_resolve(we_killed_its_head_silly)

#             lazy_resolve("UnknownStatement") # if this argument is empty, congrats! you've done the impossible, good sir!
            
#             # Unknown symbol: emit a generic node to be handled by whoever registers it
#             nodes.append(ASTNode(kind="UnknownStatement", data={"tokens": tokens}))
#         return nodes
        
# def create_parser(pm):
#     return SimpleParser(pm)

# def register(pm, module_key: str):
#     # Register the parser for .masha extension
#     pm.registry.register_parser(ext=".masha", module_path=module_key, factory_name="create_parser")

# I'm uncommented this out!
# No.

# who commented this out? my horrible and kinda cute code...
# it was horrible, not cute.

# this is shit as well. you hallucinated!
# from typing import List
# from src.core.types import ASTNode, SourceFile

# def attach_events(pm):
#     # If you want event-driven parsing or extra hooks, bind them here.
#     pass

# class SimpleParser:
#     """
#     Extremely minimal parser:
#     - Splits lines into tokens by whitespace.
#     - Treats first token as a potential symbol.
#     - Tries to lazy-load providers/executors once if not present.
#     """
#     def __init__(self, pm):
#         self.pm = pm

#     def tokenize_line(self, line: str) -> List[str]:
#         # Still "dumb": no quotes or escapes; plugins can replace this parser entirely
#         return line.strip().split()

#     def parse(self, source: SourceFile):
#         nodes = []
#         for line in source.content.splitlines():
#             if not line.strip():
#                 continue
#             tokens = self.tokenize_line(line)
#             head = tokens[0]

#             # Try resolve symbol provider (instance) immediately
#             sym_provider = self.pm.resolve_symbol(head)
#             if not sym_provider:
#                 # Attempt one-shot lazy load: try to ensure symbol and executors are loaded,
#                 # then re-resolve. Avoid infinite recursion / strange names.
#                 try:
#                     self.pm._ensure_symbol_loaded(head)

#                     # there is an import module. And if this returns something
#                     # it should return the AST kind
#                     module = self.pm.get_executors_for_kind(head)
#                     # this is because, the import statement's ast kind, is just import

#                     print(self.pm._discovered_plugin_files)

#                     # make it not none! eat its head instead!
#                     if module is None: module = head
#                     else: module = module()

#                     # executors are keyed by AST kind; we don't know it yet, but asking to
#                     # ensure executors for the head won't hurt and keeps behavior predictable.
#                     self.pm._ensure_executors_loaded_for_kind(module)
#                     print(module)
#                 except Exception:
#                     # If underlying plugin manager raised, fall back to unknown node
#                     sym_provider = None
#                 else:
#                     sym_provider = self.pm.resolve_symbol(head)

#             if sym_provider:
#                 # sym_provider is expected to be an instance (factory(self) returned)
#                 try:
#                     node = sym_provider.tokens_to_ast(tokens)
#                     nodes.append(node)
#                 except Exception:
#                     # Conversion failed — emit Unknown node so caller can handle it
#                     nodes.append(ASTNode(kind="UnknownStatement", data={"tokens": tokens}))
#                 continue

#             # Special lightweight import directive support (optional)
#             if line.startswith("import: "):
#                 # Treat remainder as a plugin key/path to attempt to import/register
#                 plugin_key = line.replace("import: ", "", 1).strip()
#                 # Try to import the plugin file if it exists among discovered ones
#                 try:
#                     self.pm._import_and_register(self.pm._abs(plugin_key))
#                 except Exception:
#                     # ignore and continue, emit UnknownStatement below
#                     pass

#             # Unknown symbol: emit a generic node to be handled by whoever registers it
#             nodes.append(ASTNode(kind="UnknownStatement", data={"tokens": tokens}))
#         return nodes

# def create_parser(pm):
#     return SimpleParser(pm)

# def register(pm, module_key: str):
#     # Register the parser for .masha extension
#     pm.registry.register_parser(ext=".masha", module_path=module_key, factory_name="create_parser")

# holy comments

from typing import List
from src.core.types import ASTNode, SourceFile

import importlib
import importlib.util
import os
import sys

def attach_events(pm):
    # Optional: hook parser events into pm.event_bus
    pass

class SimpleParser:
    """
    Minimal parser that can self-expand using ParsiePluginManager.
    - Splits by whitespace.
    - First token = potential symbol name.
    - Lazy-loads parsie executors/symbols from static/.parsie/modules.
    """
    def __init__(self, pm):
        self.pm = pm

        # Now create an isolated ParsiePluginManager instance
        from static.shared.manager import ParsiePluginManager
        self.parsie = ParsiePluginManager(pm._abs('static/.parsie/modules'))

    def tokenize_line(self, line: str) -> List[str]:
        return line.strip().split()

    def parse(self, source: SourceFile):
        nodes = []
        line_index = 0

        for line in source.content.splitlines():
            if not line.strip():
                line_index = line_index + 1
                continue

            tokens = self.tokenize_line(line)
            head = tokens[0]
            
            # Try resolve symbol via core
            sym_provider = self.pm.resolve_symbol(self.pm._abs(f"static/.parsie/modules/{head}"))

            def resolved():
                try:
                    node = sym_provider.tokens_to_ast(tokens)
                    # if node.kind == "Outerlands":
                    #     node = sym_provider.tokens_to_ast(tokens, source.content.splitlines(), line_index)

                    nodes.append(node)
                except Exception:
                    pass

            # Try parsie-based fallback
            if not sym_provider:
                # Parsie symbols are in its own registry
                sym_provider = self.parsie.get_symbol_provider(head)
                resolved()

            if sym_provider:
                resolved()
                line_index = line_index + 1
                continue

            # Unknown symbol fallback
            nodes.append(ASTNode(kind="UnknownStatement", data={"tokens": tokens}))

        return nodes


def create_parser(pm):
    return SimpleParser(pm)


def register(pm, module_key: str):
    # Register the .masha parser in the main registry
    pm.registry.register_parser(ext=".masha", module_path=module_key, factory_name="create_parser")
