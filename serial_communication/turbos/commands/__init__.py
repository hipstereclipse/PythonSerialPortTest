"""
Initializes all turbo commands and makes them available through a single import point.
"""
from serial_communication.turbos.commands.tc600_commands import TC600Command

# Make all commands available at the module level
__all__ = [
    'TC600Command'
]

# Create a mapping of gauge types to their command classes
TURBO_COMMAND_MAP = {
   'TC600': TC600Command
}

def get_command_class(turbo_type: str):
    """Get the command class for a specific turbo type."""
    if turbo_type not in TURBO_COMMAND_MAP:
        raise ValueError(f"Unknown gauge type: {turbo_type}")
    return TURBO_COMMAND_MAP[turbo_type]