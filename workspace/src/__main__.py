# masha_lang/__main__.py
import os
import sys
from typing import Callable
from .core.plugins_manager import PluginManager
from nakuritycore.utils.tracer import TracerConfig, Tracer

from nakuritycore.utils.tracer import TracerConfig, Tracer
from .shared.constants import MANAGERS, BUSES

tracy = Tracer(TracerConfig(
    project_root=os.getcwd(),
    name="Tracy! the neighbor's kid!",
    log_file_base="nakurity-lang.log",
    include_paths=["src", "static"],
))

#sys.settrace(tracy.trace)

def dependent():
    eventbus = BUSES.get('eventbus')
    pm = MANAGERS.get('plugin-manager')
    pm.load_config()

    def nonstandalone(function: Callable):
        function(pm, sys.argv)
    pass

    try:
        # Creates a listener first, so when the event fires, 
        eventbus.on( # the listener would catch it
            'runner:function.return',
            nonstandalone
        )

        # import the plugin
        pm.get_plugin('> .needy/modules/runner.py')

        # Verify if the event actually exists and got registered.
        runner_exists = eventbus.verify().get('event_exists')('runner:function.return')

        if not runner_exists: # If it didn't exist, print an error.
            print("No runner module registered. Did you enable .needy/modules?")
            print('Defaulting to standalone runner module.')
            eventbus.emit('nakurity-source:main.error', error='Runner plugin not found, defaulting to standalone module')
            sys.exit(1)

    except Exception as e:
        eventbus.emit("nakurity-source:main.error", error=e)
        raise

def standalone(root_dir: str):
    installed = [
        os.path.join(root_dir, 'static')
    ]
    for path in installed:
        if not os.path.exists(path):
            installed.remove(path)
            print(f"warning: source {path} not downloaded")

    if installed.count != 0: return
    
    print('hint: try running "nakurity download"')
    if sys.argv.includes('download'):
        args = sys.argv
        args.remove('download')
        
        from .utils import download
        sys.exit(download.handle(args))

if __name__ == "__main__":
    root_dir = os.getcwd()
    standalone(root_dir)
    dependent()
