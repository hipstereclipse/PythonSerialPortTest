"""
opg_commands.py

Defines command definitions for the OPG550 optical plasma gauge.
"""

from serial_communication.param_types import CommandDefinition

class OPGCommand:
    """
    Contains command definitions for the OPG550 optical plasma gauge.
    """
    PRESSURE = CommandDefinition(
        pid=14000,
        name="pressure",
        description="Read total pressure",
        read=True,
        write=False
    )
    PLASMA_STATUS = CommandDefinition(
        pid=12003,
        name="plasma_status",
        description="Get plasma status",
        read=True,
        write=False
    )
    PLASMA_CONTROL = CommandDefinition(
        pid=12002,
        name="plasma_control",
        description="Control plasma",
        read=False,
        write=True
    )
    SELF_TEST = CommandDefinition(
        pid=11000,
        name="self_test",
        description="Run self diagnostic",
        read=True,
        write=False
    )
    ERROR_STATUS = CommandDefinition(
        pid=11002,
        name="error_status",
        description="Get error count",
        read=True,
        write=False
    )
    SOFTWARE_VERSION = CommandDefinition(
        pid=10004,
        name="software_version",
        description="Read firmware version",
        read=True,
        write=False
    )
