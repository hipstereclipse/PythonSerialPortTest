"""
bcg552_commands.py

Defines command definitions for BCG552 triple gauge devices.
Each command is standardized using the CommandDefinition data class.
"""

from serial_communication.param_types import CommandDefinition, ParamType

class BCG552Command:
    """
    Contains command definitions for BCG552 triple gauge devices.
    """
    PRESSURE = CommandDefinition(
        pid=221,
        name="pressure",
        description="Read pressure measurement",
        read=True,
        write=False,
        continuous=True
    )

    TEMPERATURE = CommandDefinition(
        pid=222,
        name="temperature",
        description="Read sensor temperature",
        read=True,
        write=False
    )

    ZERO_ADJUST = CommandDefinition(
        pid=417,
        name="zero_adjust",
        description="Perform zero adjustment",
        read=False,
        write=True
    )

    SOFTWARE_VERSION = CommandDefinition(
        pid=218,
        name="software_version",
        description="Read software version",
        read=True,
        write=False
    )

    SERIAL_NUMBER = CommandDefinition(
        pid=207,
        name="serial_number",
        description="Read serial number",
        read=True,
        write=False
    )

    ERROR_STATUS = CommandDefinition(
        pid=228,
        name="error_status",
        description="Read error status",
        read=True,
        write=False
    )
