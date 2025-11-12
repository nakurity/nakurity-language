# masha_lang/__main__.py
import os
import sys
from core.plugin_manager import PluginManager
from core.types import SourceFile

def read_source(path: str) -> SourceFile:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    ext = os.path.splitext(path)[1]
    return SourceFile(path=path, content=content, extension=ext)

def main():
    root_dir = os.getcwd()
    pm = PluginManager(root_dir=root_dir)
    pm.load_config()
    pm.run_autorun()   # autorun modules handle flags, setup, etc.

    # Hand off to a runner plugin/module
    runner = pm.resolve_symbol("__runner__")
    if runner is None:
        print("No runner module registered. Did you enable .needy/modules?")
        sys.exit(1)

    runner.run(pm, sys.argv)

if __name__ == "__main__":
    main()
