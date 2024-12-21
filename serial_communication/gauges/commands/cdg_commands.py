"""
Holds command definitions for CDG gauges (CDG025D, CDG045D, etc.).
"""

from serial_communication.param_types import CommandDefinition, ParamType

class CDGCommand:
    """
    Lists all commands specific to CDG gauges.
    """
    PRESSURE = CommandDefinition(
        pid=0xDD,
        name="pressure",
        description="Read pressure measurement",
        read=True,
        write=False,
        continuous=True
    )
    TEMPERATURE = CommandDefinition(
        pid=0xDE,
        name="temperature",
        description="Read sensor temperature",
        read=True,
        write=False
    )
    ZERO_ADJUST = CommandDefinition(
        pid=0x02,
        name="zero_adjust",
        description="Perform zero adjustment",
        read=False,
        write=True
    )
    FULL_SCALE = CommandDefinition(
        pid=0x03,
        name="full_scale",
        description="Set full scale value",
        read=True,
        write=True,
        param_type=ParamType.FLOAT
    )
    SOFTWARE_VERSION = CommandDefinition(
        pid=0x10,
        name="software_version",
        description="Read software version",
        read=True
    )
    UNIT = CommandDefinition(
        pid=0x01,
        name="unit",
        description="Get/set pressure unit",
        read=True,
        write=True,
        param_type=ParamType.UINT8
    )
    FILTER = CommandDefinition(
        pid=0x02,
        name="filter",
        description="Get/set filter mode",
        read=True,
        write=True,
        param_type=ParamType.UINT8
    )
