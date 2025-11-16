# This is separated from the activation file, for clarity
from .activation import initialize

CONSTANTS = initialize()
MANAGERS = CONSTANTS.get('managers')
BUSES = CONSTANTS.get('buses', {})