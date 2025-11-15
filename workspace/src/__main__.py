# masha_lang/__main__.py
import os
import sys

from pathlib import Path
from .core.plugins_manager import PluginManager
from nakuritycore.utils.tracer import TracerConfig, Tracer

from nakuritycore.utils.tracer import TracerConfig, Tracer

tracy = Tracer(TracerConfig(
    project_root=os.getcwd(),
    name="Tracy! the neighbor's kid!",
    log_file_base="nakurity-lang.log",
    include_paths=["src", "static"],
))

# sys.settrace(tracy.trace)

def dependencies(root_dir: str):
    pm = PluginManager(root_dir=root_dir)
    pm.load_config()
    pm.run_autorun()   # autorun modules handle flags, setup, etc.

    # Hand off to a runner plugin/module
    runner = pm.resolve_symbol("__runner__")
    if runner is None:
        print("No runner module registered. Did you enable .needy/modules?")
        sys.exit(1)

    runner(pm, sys.argv)

def standalone(toot_dir: str):
    installed = [
        os.path.join(root_fir, 'static')
    ]
    for path in installed:
        if !os.path.exists(path):
            installed.remove(path)
            print(f"warning: source {path} not downloaded")

    if installed.count != 0: return;
    
    print('hint: try running "nakurity download"')
    if sys.argv.includes('download'):
        args = sys.argv
        args.remove('download')
        
        from utils import download
        sys.exit(download.handle(args))

if __name__ == "__main__":
    root_dir = os.getcwd()
    standalone(root_dir)
    dependencies(root_dir)
