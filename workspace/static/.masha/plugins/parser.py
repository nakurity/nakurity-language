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

from typing import List, Callable, Optional
from src.core.plugins_manager import PluginManager
from src.core.types import ASTNode, SourceFile

class ParserError(Exception):
    pass

def attach_events(pm):
    # Optional: hook parser events into pm.event_bus
    pass

class Parser:
    """
    Minimal parser that can self-expand using ParsiePluginManager.
    - Splits by whitespace.
    - First token = potential symbol name.
    - Lazy-loads parsie executors/symbols from static/.parsie/modules.
    """
    def __init__(self, pm: PluginManager):
        self.pm = pm

        # Now create an isolated ParsiePluginManager instance
        from static.shared.manager import ParsiePluginManager
        self.parsie = ParsiePluginManager(self.pm.event_bus)

    def tokenize_line(self, line: str) -> List[str]:
        return line.strip().split()

    def parse(self, source: SourceFile):
        nodes = []
        line_index = 0
        
        interrupt_moment = 'before_load'

        def interrupt(fn: Optional[Callable]) -> dict | None:
            nonlocal interrupt_moment
            if not callable(fn): # if function is not callable
                # assume the caller is asking information.

                # This just says an interrupt happened, and the
                # interrupting module wanted information. As if
                # the other events wasn't already giving enough
                # information.
                self.pm.event_bus.emit(
                    f'parser:interrupt.request.{interrupt_moment}_parameters'
                )

                return { # Returns the interrupt information
                            
                    'symbol': head, # The symbol head is what
                    # the parser uses to identify and resolve
                    # the symbol to which parsie module. This
                    # is done by name matching the py files.

                    # This sub-dict contains the full line
                    # context. So the interrupting module can
                    # do something with it.
                    'line': {
                        # Line index
                        'index': line_index,

                        # Full line
                        'full': line
                    },

                    # Returns parsie, so the interrupting module
                    # can interact with the environment that loads
                    # the modules.
                    'parsie': self.parsie,
                }
                
            self.pm.event_bus.emit(
                f'parser:interrupt.signal.{interrupt_moment}',
                interrupt_function=fn
            )

            # if interrupt moment says its been interrupted. then
            # stop the normal flow of the parser
            interrupt_moment = 'interrupted'
                
            # Since it is already checked above, if its callable or not
            # (i.e. is it a function or not), it should've been function
            # if it passed to this line. Otherwise it'd be caught by the
            # if condition above there.
            fn(
                # The interrupt function will provide a few params for the
                # interrupting module. Inside a params dict.
                params={
                    # The params dict should be identifical the the dict
                    # provided by the interrupt function, when called without
                    # giving a function for the interrupt function to execute.
        
                    # It gives the head of the symbol, which is the part
                    # of an line, that is separated by a space. And is the
                    # starting item. Like print "hello world", print is
                    # the head. and hello world is the parameters.
                    'symbol': head,

                    # These are the line items. It provides the current
                    # line number, and the full line contents.
                    'line': {
                        'index': line_index,
                        'full': line
                    },

                    # Parsie contains a bunch of stuff that Parser uses
                    # to register and load the provider for these symbols,
                    # since this module is interrupting that flow. It
                    # directly bypasses parsie. So this is given so the
                    # interrupting module can still use it.
                    'parsie': self.parsie
                },

                events=[
                    # This list should contain events that parser still
                    # hasn't fired. And assuming there are listeners waiting
                    # for those events. Like from other plugins or modules
                    # listening for those events, it is standard for the
                    # interrupting module to fire those events themselves,
                    # so other plugins / modules don't break because of this.

                    'parser:node', # This fires an event that provides the resolved
                    # node for other listening plugins. Zero privacy, I know.

                    'parser:symbol:missing', # This event is optional, since
                    # it is usually only fired when parser could not resolve
                    # a symbol on its own.

                    'parser:symbol:found', # This event is usually an expected
                    # behavior, since it obviously says parser has found and
                    # resolved the symbol on its own.

                    'parser:symbol.after_load', # This event is fired after
                    # parser has loaded and resolved everything for a sumbol,
                    # and is continuing to the next symbol.

                    'parser:symbol.before_load', # This event fires before
                    # parser tries to resolve and load a symbol.
                ]
            )
            
        self.pm.event_bus.on( # This is so plugins can interrupt Parser
            # and inject their own code. Could be useful for adding an
            # multi-line definition helper. Since this listener skips
            # the traditional Parser flow. And does not run the code below.
            'parser:interrupt.symbol.before_load',

            # This function either calls the function that is provided
            # by the interrupting module. Or returns useful information
            # from parser, if no function is given to it.
            interrupt

        ) # This event needs to be above the code that registers the parsie
        # plugin, because it needs to skip the traditional flow of the parser.

        # Emit full source BEFORE parsing starts
        self.pm.event_bus.emit('parser:full_source_available', lines=source.content.splitlines())

        for line in source.content.splitlines():

            if not line.strip():
                line_index = line_index + 1
                continue

            tokens = self.tokenize_line(line)
            head = tokens[0]

            self.pm.event_bus.emit(
                "parser:line",
                line=line,
                line_index=line_index,
                tokens=tokens
            )

            # This event fires before parser loads
            # everything.
            self.pm.event_bus.emit(
                'parser:symbol.before_load',
                symbol=head,
                line=line,
                line_index=line_index,
                tokens=tokens,
            )

            if interrupt_moment == 'interrupted':
                interrupt_moment = 'before_load'
                line_index = line_index + 1
                continue # Stop before it reaches normally

            # This is placed below the interrupt system, so that it is skipped. Since the
            # interrupt system is supposed to be used for multi-line definition. And this
            # code below, only support one line definition.
            self.parsie.register_plugin_file(head, self.pm._abs(f"static/.parsie/modules/{head}.py"))
            
            # Try resolve symbol via core
            sym_provider = self.parsie.get_symbol_provider(head)

            def resolve():
                try:
                    # This assumes the module has a the function
                    # below. It is required. This is why its in
                    # a try catch function.
                    node = sym_provider.tokens_to_ast(tokens)

                    # This fires an event, so
                    # modules can listen to it.
                    self.pm.event_bus.emit(
                        "parser:node",
                        node=node,
                        line_index=line_index
                    )

                    # This should append the node. That gets
                    # returned.
                    nodes.append(node)
                except Exception:
                    pass

            # This event fires to say parser has completed
            # loading, and now is onto validation of the
            # loaded symbol. This means parser is checking
            # if the symbol has actually loaded or not.
            self.pm.event_bus.emit(
                'parser:symbol.after_load',
                line_index=line_index,
                line=line
            )

            interrupt_moment = 'after_load'
            self.pm.event_bus.emit(
                'parser:interrupt.symbol.after_load',

                # Run the same function, but this time.
                # its set to emit events as after load.
                interrupt
            )

            # Fail to resolve, sends an event
            if not sym_provider:

                # This is so processes can listen to it
                # and make other modules like a crash report
                # plugin for the parser plugin.
                self.pm.event_bus.emit(
                    "parser:symbol.missing",
                    symbol=head,
                    line_index=line_index
                )

                # Raise an Exception
                raise ParserError(f"Invalid Symbol: unable to resolve '{head}' symbol")

            if sym_provider:
                resolve() # This is a function, because it used to
                # have two locations calling it. I'll keep it like this.

                # Same reason as always
                self.pm.event_bus.emit(
                    "parser:symbol.found",
                    symbol=head,
                    line_index=line_index
                )

                # Line index is not particularly used by the Parser
                # but can be useful for other modules listening to
                # parser event signals, and trying to interrupt.
                line_index = line_index + 1
                continue

            # Unknown symbol fallback
            nodes.append(ASTNode(kind="UnknownStatement", data={"tokens": tokens}))

        return nodes

def create_parser(pm):
    return Parser(pm)

def register(pm, module_key: str):
    pm.event_bus.emit(
        'parser:registered',
        module_key=module_key
    )