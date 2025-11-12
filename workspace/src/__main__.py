# masha_lang/__main__.py
import sys
import os
from core.plugin_manager import PluginManager
from core.types import SourceFile

def read_source(path: str) -> SourceFile:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    ext = os.path.splitext(path)[1]
    return SourceFile(path=path, content=content, extension=ext)

def main():
    # Root is the project directory containing .masha/config.json
    root_dir = os.getcwd()
    pm = PluginManager(root_dir=root_dir)
    pm.load_config()
    pm.register_from_config()

    if len(sys.argv) < 2:
        print("Usage: nakurity-lang <source_file>")
        sys.exit(1)

    src = read_source(sys.argv[1])

    # Lazy get parser based on extension from config
    parser = pm.get_parser_for_extension(src.extension)
    if parser is None:
        print(f"No parser registered for extension: {src.extension}")
        sys.exit(2)

    # Parse: parser can request symbol providers lazily via plugin manager
    ast = parser.parse(src)

    # Execute: walk AST; for each node kind, resolve executors lazily
    def execute_node(node):
        executors = pm.get_executors_for_kind(node.kind)
        if not executors:
            raise RuntimeError(f"No executor for AST kind: {node.kind}")
        # Pick the first that claims it can handle
        for ex in executors:
            if ex.can_handle(node):
                return ex.execute(node)
        raise RuntimeError(f"No executor accepted AST kind: {node.kind}")

    if isinstance(ast, list):
        for node in ast:
            execute_node(node)
    else:
        execute_node(ast)

if __name__ == "__main__":
    main()
