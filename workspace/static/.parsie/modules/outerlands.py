from src.core.types import ASTNode
from pathlib import Path
from re import compile
import os
import ast
import runpy

def outerlands_import(path, **kwargs):
    """
    Loads a Python file and injects kwargs into its global namespace.
    Returns the global namespace dictionary after execution.
    """
    # Prepare the global namespace
    globs = {
        "__name__": "__outerlands_import__",
        "__file__": str(path),
        **kwargs
    }
    
    # Execute the file
    runpy.run_path(str(path), init_globals=globs)
    return globs

class OuterlandsSymbolProvider:
    # Matches require["something"]
    REQUIRE_PATTERN = compile(
        r'^require\[\s*"(?P<path>[^"]+)"\s*\]'
    )

    # Matches boarding['func_name'] or boarding (no brackets)
    BOARDING_PATTERN = compile(
        r'^boarding(?:\[\s*[\'"](?P<func_name>[^"\']+)[\'"]\s*\])?'
    )

    # Matches optional argument call: (msg='aaa', a=1)
    CALL_PATTERN = compile(
        r'^\((?P<args>.*)\)$'
    )

    def __init__(self, pm):
        self.pm = pm
        
        # Multiline capture state
        self.capturing_multiline = False
        self.multiline_header_line = None
        self.multiline_start_index = -1
        self.multiline_header_tokens = []
        self.multiline_config = {}
        self.multiline_payload_lines = []
        
        self._setup_listeners()

    def _setup_listeners(self):
        """Listen to parser events to handle multiline blocks"""
        
        # Intercept every line during multiline capture
        def check_and_capture(symbol, line, line_index, tokens):
            # If we're capturing multiline content
            if self.capturing_multiline:
                stripped = line.strip()
                
                # Check if we've reached the end
                if stripped == "[finished-definition]":
                    # Build the final node
                    self._finalize_multiline_node(line_index)
                    return
                
                # Check for config lines (start with .)
                if stripped.startswith(".") and not self.multiline_payload_lines:
                    parts = stripped[1:].split(" ", 1)
                    key = parts[0]
                    val = parts[1].strip() if len(parts) > 1 else ""
                    self.multiline_config[key] = val
                else:
                    # Payload line - dedent by 2 spaces if present
                    if line.startswith("  "):
                        self.multiline_payload_lines.append(line[2:])
                    else:
                        self.multiline_payload_lines.append(line)
                
                # Emit interrupt to skip this line
                def skip_line(params, events):
                    pass
                
                self.pm.event_bus.emit('parser:interrupt.symbol.before_load', skip_line)
                return
            
            # Check if this line starts a multiline block
            if symbol == 'outerlands' and '[below]' in line:
                # Start capturing
                self.capturing_multiline = True
                self.multiline_header_line = line
                self.multiline_start_index = line_index
                self.multiline_header_tokens = tokens
                self.multiline_config = {}
                self.multiline_payload_lines = []
                
                # Emit interrupt for the header line
                def skip_header(params, events):
                    pass
                
                self.pm.event_bus.emit('parser:interrupt.symbol.before_load', skip_header)
        
        self.pm.event_bus.on('parser:symbol.before_load', check_and_capture)

    def _finalize_multiline_node(self, end_index):
        """Build and emit the final multiline node"""
        
        # Parse the header
        header = self.multiline_header_line.split('[below]')[0].strip()
        header_tokens = header.split()
        initial_ast = self.tokens_to_ast(header_tokens)
        
        # Build the complete node
        node = ASTNode(
            kind="Outerlands",
            data={
                **initial_ast.data,
                "config": self.multiline_config,
                "text": "\n".join(self.multiline_payload_lines),
                "multiline": True
            }
        )
        
        # Emit the expected events
        self.pm.event_bus.emit('parser:node', node=node, line_index=self.multiline_start_index)
        self.pm.event_bus.emit('parser:symbol:found', symbol='outerlands', line_index=self.multiline_start_index)
        self.pm.event_bus.emit('parser:symbol.after_load', line_index=self.multiline_start_index, line=self.multiline_header_line)
        
        # Reset capture state
        self.capturing_multiline = False
        self.multiline_header_line = None
        self.multiline_start_index = -1
        self.multiline_header_tokens = []
        self.multiline_config = {}
        self.multiline_payload_lines = []
        
        # Emit interrupt for [finished-definition] line itself
        def skip_end(params, events):
            pass
        
        self.pm.event_bus.emit('parser:interrupt.symbol.before_load', skip_end)

    def tokens_to_ast(self, tokens):
        """
        Supports:
            outerlands require["root/a.py"]
            outerlands require["root/a.py"](msg="aa")
            outerlands boarding['function_name'](msg='aa')
            outerlands boarding
        """
        if len(tokens) < 2:
            return ASTNode(kind="Outerlands", data={"error": "missing subcommand"})

        raw = " ".join(tokens[1:]).strip()

        # Check for boarding syntax
        boarding_match = self.BOARDING_PATTERN.match(raw.split('(')[0].strip())
        if boarding_match:
            func_name = boarding_match.group('func_name')
            
            # Parse optional arguments
            args = {}
            if '(' in raw:
                args_part = '(' + raw.split('(', 1)[1]
                try:
                    args_ast = ast.parse(f"f{args_part}", mode="eval")
                    for kw in args_ast.body.keywords:
                        args[kw.arg] = ast.literal_eval(kw.value)
                except Exception:
                    args["__parse_error__"] = args_part.strip()
            
            return ASTNode(
                kind="Outerlands",
                data={
                    "alias": "boarding",
                    "function_name": func_name,
                    "args": args
                }
            )

        # Check for require syntax
        if "(" in raw:
            before, after = raw.split("(", 1)
            after = "(" + after
        else:
            before, after = raw, None

        match = self.REQUIRE_PATTERN.match(before.strip())
        if not match:
            return ASTNode(
                kind="Outerlands",
                data={
                    "alias": "unknown",
                    "raw": raw,
                    "error": "Unsupported outerlands syntax"
                }
            )

        path = match.group("path")

        # Replace root/ prefix
        if path.startswith("root"):
            root_dir = Path(
                Path(os.path.abspath(__file__)) /
                ".." / ".." / ".." / ".." / ".."
            ).resolve()
            path = path.replace("root", str(root_dir), 1)

        resolved = Path(path).resolve()

        # Parse optional arguments
        args = {}
        if after:
            try:
                args_ast = ast.parse(f"f{after}", mode="eval")
                for kw in args_ast.body.keywords:
                    args[kw.arg] = ast.literal_eval(kw.value)
            except Exception:
                args["__parse_error__"] = after.strip()

        return ASTNode(
            kind="Outerlands",
            data={
                "alias": "require",
                "path": resolved,
                "args": args
            }
        )


class OuterlandsExecutor:
    def __init__(self, pm):
        self.pm = pm

    def can_handle(self, node: ASTNode) -> bool:
        return node.kind == "Outerlands"
    
    def execute(self, node: ASTNode):
        alias = node.data.get("alias", "")
        
        if alias == "require":
            path = node.data.get("path")
            args = node.data.get("args", {})

            result = outerlands_import(path, **args)

            # Optionally: emit event so the rest of PM can use what was loaded
            self.pm.event_bus.emit(
                "outerlands:imported",
                path=path,
                namespace=result
            )
        
        elif alias == "boarding":
            # Execute boarding code
            code = node.data.get("text", "")
            args = node.data.get("args", {})
            func_name = node.data.get("function_name")
            
            # Create execution context
            exec_globals = {"__name__": "__outerlands__"}
            exec_globals.update(args)
            
            # Execute the code
            exec(code, exec_globals)
            
            # If function_name specified, it's a function definition
            # Otherwise it's auto-run code
            if func_name:
                # Store function for later use
                if func_name in exec_globals:
                    self.pm.event_bus.emit(
                        'outerlands:function_defined',
                        name=func_name,
                        function=exec_globals[func_name]
                    )


def create_outerlands_symbol(pm):
    return OuterlandsSymbolProvider(pm)

def create_executor(pm):
    return OuterlandsExecutor(pm)

def register(pm, module_key: str):
    pm.registry.register_executor(
        kind="Outerlands",
        module_path=module_key,
        factory_name="create_executor"
    )
    pm.registry.register_symbol(
        symbol_name="outerlands",
        module_path=module_key,
        factory_name="create_outerlands_symbol"
    )