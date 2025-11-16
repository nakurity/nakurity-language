# local module imports will go here
from ..core.plugins_manager import PluginManager
from ..core.events import EventBus

# import only what's needed
from pathlib import PosixPath
from os import path

# This function initializes everything for nakurity
def initialize() -> dict:
    """Initialize all relevant modules for this project"""

    def root_directory() -> str:
        """Gets the root directory of the project"""
        # walk up until the workspace folder, not outside nakurity-language
        root_directory = PosixPath(__file__) / '..' / '..' / '..'

        # resolve the directory correctly
        #
        # if not, it'll output something like this:
        #  > nakurity-language/workspace/src/shared/activation.py/../../..
        root_directory = path.abspath(root_directory)
        
        # /workspaces/nakurity-language/workspace
        # is considered a working environment where
        # the prototyped source code and the modules
        # will live.
        # 
        # Initialize will provide the directory for
        # all other modules
        return root_directory
    
    # this is returning a tuple for expandablity, in the future
    def buses() -> dict:
        """Initializes the buses (i.e. EventBus, and etc)"""
        EVENT_BUS = EventBus() # This initializes it.
        return {
            # Returns the event bus constant
            'eventbus': EVENT_BUS
        }
    
    buses_var = buses() # initializes this firsthand, so the managers
                        # function can grab the event bus instance

    # This is a function for asthestics
    def managers() -> dict:
        """Initializes the core managers for nakurity"""
        return {
            'plugin-manager': PluginManager(
                root_dir=root_directory(),
                event_bus=buses_var.get('eventbus', EventBus)
            )
        }
    
    return {
        # Runs the function first, so a string
        # would be returned instead of a callable.
        'root_directory': root_directory(),

        # Same reason as the 'root_directory' one.
        'managers': managers(),

        # This takes the already initialized
        # bus_var and returns it. this is so
        # that no reinitialization occurs
        'buses': buses_var
    }

def activate():
    pass