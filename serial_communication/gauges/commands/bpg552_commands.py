"""
Defines command definitions for BPG552 DualGauge.
"""
from serial_communication.param_types import CommandDefinition, ParamType

class BPG552Command:
    """
    Stores all command definitions for Pfeiffer BPG552 DualGauge.
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
        description="Execute zero adjustment",
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
    EMISSION_STATUS = CommandDefinition(
        pid=533,
        name="emission_status",
        description="Get emission status",
        read=True,
        write=False
    )
    DEGAS = CommandDefinition(
        pid=529,
        name="degas",
        description="Control degas function",
        read=False,
        write=True,
        param_type=ParamType.BOOL
    )
    EMISSION_CURRENT = CommandDefinition(
        pid=530,
        name="emission_current",
        description="Get/set emission current",
        read=True,
        write=True
    )
