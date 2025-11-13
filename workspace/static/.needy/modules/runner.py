# static/.needy/modules/runner.py
import sys
import os
from src.core.types import SourceFile

def read_source(path: str) -> SourceFile:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    ext = os.path.splitext(path)[1]
    return SourceFile(path=path, content=content, extension=ext)

def run(pm, argv):
    if len(argv) < 2:
        print("Usage: nakurity-lang <source_file> [:bare] | nakurity-lang download [static.zip]")
        sys.exit(1)

    # handle :bare, download, etc. here
    # if argv[1] == "download":
    #     from . import download
    #     return download.handle(pm.root_dir, argv[2:] if len(argv) > 2 else [])

    bare = any(arg == ":bare" for arg in argv)
    if bare:
        pm.autoload_the_needies = False


    src_path = next((a for a in argv[1:] if not a.startswith(":")), None)
    if not src_path:
        print("No source file provided")
        sys.exit(1)

    src = read_source(src_path)
    parser = pm.get_parser_for_extension(src.extension)
    if parser is None:
        print(f"No parser registered for extension: {src.extension}")
        sys.exit(2)

    ast = parser.parse(src)

    for node in (ast if isinstance(ast, list) else [ast]):
        executors = parser.parsie.get_executors_for_kind(node.kind)
        if not executors:
            raise RuntimeError(f"No executor for AST kind: {node.kind}")
        for ex in executors:
            if ex.can_handle(node):
                ex.execute(node)
                break


# static/.needy/modules/runner.py
def register(pm, module_key=None):
    pm.registry.register_symbol("__runner__", module_key, "run")
