"""
__init__.py

Initializes the turbos package by making available all turbo commands and protocols.
"""

from serial_communication.turbos.commands.tc600_commands import TC600Command

__all__ = [
    'TC600Command'
]

TURBO_COMMAND_MAP = {
    'TC600': TC600Command
}

def get_command_class(turbo_type: str):
    """
    Retrieves the command class for a specific turbo type.

    Args:
        turbo_type: The type of turbo pump (e.g., "TC600").

    Returns:
        The corresponding command class.

    Raises:
        ValueError: If the turbo type is unknown.
    """
    if turbo_type not in TURBO_COMMAND_MAP:
        raise ValueError(f"Unknown gauge type: {turbo_type}")
    return TURBO_COMMAND_MAP[turbo_type]
