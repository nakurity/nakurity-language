# static/.needy/modules/runner.py
import sys
import os
from src.core.types import SourceFile

def read_source(path: str) -> SourceFile:
    """Read source file and return SourceFile object"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    ext = os.path.splitext(path)[1]
    return SourceFile(path=path, content=content, extension=ext)

def run(pm, argv):
    """Main runner function that orchestrates parsing and execution"""
    if len(argv) < 2:
        print("Usage: nakurity <source_file> [:bare] | nakurity-lang download [static.zip]")
        sys.exit(1)

    # Check for special commands
    if argv[1] == "download":
        # TODO: Implement download functionality
        print("Download functionality not yet implemented")
        sys.exit(1)

    # Check for :bare flag (disables auto-loading)
    bare = any(arg == ":bare" for arg in argv)
    if bare:
        # In bare mode, we expect plugins to be explicitly loaded
        pm.event_bus.emit("runner:bare_mode_enabled")

    # Extract source file path (skip flags starting with :)
    src_path = next((a for a in argv[1:] if not a.startswith(":")), None)
    if not src_path:
        print("No source file provided")
        sys.exit(1)

    # Emit event before reading source
    pm.event_bus.emit("runner:before_read_source", path=src_path)
    
    # Read the source file
    try:
        src = read_source(src_path)
        pm.event_bus.emit("runner:after_read_source", source=src)
    except FileNotFoundError:
        print(f"Error: Source file not found: {src_path}")
        sys.exit(2)
    except Exception as e:
        print(f"Error reading source file: {e}")
        sys.exit(2)

    # Get parser for the file extension
    pm.event_bus.emit("runner:before_get_parser", extension=src.extension)
    
    # Load the parser plugin for this extension
    # For .masha files, load the parser_simple plugin
    parser_plugin_map = {
        ".masha": "@.masha/plugins/parser.py"
    }
    
    parser_plugin_path = parser_plugin_map.get(src.extension)
    if not parser_plugin_path:
        print(f"No parser registered for extension: {src.extension}")
        sys.exit(2)
    
    # Load the parser plugin
    try:
        parser_module = pm.get_plugin(parser_plugin_path)
        # Get the create_parser factory function
        create_parser = getattr(parser_module, "create_parser", None)
        if not create_parser:
            print(f"Parser plugin missing 'create_parser' function")
            sys.exit(2)
        
        # Create parser instance
        parser = create_parser(pm)
        pm.event_bus.emit("runner:after_get_parser", parser=parser, extension=src.extension)
    except Exception as e:
        print(f"Error loading parser: {e}")
        sys.exit(2)

    # Parse the source file
    pm.event_bus.emit("runner:before_parse", source=src)
    try:
        ast = parser.parse(src)
        pm.event_bus.emit("runner:after_parse", ast=ast)
    except Exception as e:
        print(f"Parse error: {e}")
        pm.event_bus.emit("runner:parse_error", error=e, source=src)
        sys.exit(3)

    # Execute the AST nodes
    pm.event_bus.emit("runner:before_execute", ast=ast)
    
    # Normalize AST to list
    nodes = ast if isinstance(ast, list) else [ast]
    
    for node_index, node in enumerate(nodes):
        pm.event_bus.emit("runner:before_execute_node", node=node, index=node_index)
        
        # Get executors for this node kind from parsie
        executors = parser.parsie.get_executors_for_kind(node.kind)
        
        if not executors:
            print(f"Warning: No executor found for AST kind: {node.kind}")
            pm.event_bus.emit("runner:no_executor", node=node, kind=node.kind)
            continue
        
        # Try each executor until one handles it
        executed = False
        for executor in executors:
            if executor.can_handle(node):
                try:
                    executor.execute(node)
                    pm.event_bus.emit("runner:after_execute_node", node=node, executor=executor)
                    executed = True
                    break
                except Exception as e:
                    print(f"Execution error in {node.kind}: {e}")
                    pm.event_bus.emit("runner:execute_error", node=node, executor=executor, error=e)
                    sys.exit(4)
        
        if not executed:
            print(f"Warning: No executor could handle node: {node.kind}")
            pm.event_bus.emit("runner:node_not_handled", node=node)

    pm.event_bus.emit("runner:after_execute", ast=ast)
    pm.event_bus.emit("runner:complete")


def register(pm, module_key=None):
    """Register the runner with the plugin manager"""
    # Simply store the module key for reference
    # The runner is called directly from __main__.py
    pm.event_bus.emit("runner:registered", module_key=module_key)

    # Register the event as an verifiable evebt that it exists and
    # the runner.py module has sucessfully registered.
    pm.event_bus.register().get('event')('runner:function.return')
    pm.event_bus.emit( # Fire an event to send the function to __main__.py
        'runner:function.return',
        function=run
    )