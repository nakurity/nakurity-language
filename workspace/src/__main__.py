# masha_lang/__main__.py
import os
import sys
from .core.plugins_manager import PluginManager
from nakuritycore.utils.tracer import TracerConfig, Tracer

from nakuritycore.utils.tracer import TracerConfig, Tracer

tracy = Tracer(TracerConfig(
    project_root=os.getcwd(),
    name="Tracy! the neighbor's kid!",
    log_file_base="nakurity-lang.log",
    include_paths=["src", "static"]
))

sys.settrace(tracy.trace)

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

    runner(pm, sys.argv)

if __name__ == "__main__":
    main()