# serial_communication/gauges/commands/psg550_commands.py
"""
Defines command definitions for PSG550 Pirani/Piezo combination gauge.
"""
from serial_communication.param_types import CommandDefinition, ParamType


class PSG550Command:
    """
    Holds command definitions for PSG550 Pirani/Piezo combination gauge.
    """
    PRESSURE = CommandDefinition(
        pid=221,
        name="pressure",
        description="Read pressure measurement (Fixs32en20)",
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

    PIRANI_FULL_SCALE = CommandDefinition(
        pid=33000,
        name="pirani_full_scale",
        description="Read Pirani full scale",
        read=True,
        write=False
    )

    PIRANI_ADJUST = CommandDefinition(
        pid=417,
        name="pirani_adjust",
        description="Execute Pirani adjustment",
        read=False,
        write=True
    )