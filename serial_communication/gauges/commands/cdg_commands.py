"""
cdg_commands.py

Defines command definitions for CDG gauges (Capacitance Diaphragm Gauges)
with additional support for model identification.
"""

from serial_communication.param_types import CommandDefinition, ParamType

class CDGCommand:
    """
    Contains enhanced command definitions for all CDG gauge variants.
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
        read=True,
        write=False
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

    DATA_TX_MODE = CommandDefinition(
        pid=0x00,
        name="data_tx_mode",
        description="Toggle data transmission mode",
        read=True,
        write=True,
        param_type=ParamType.UINT8
    )

    ZERO_ADJUST_VALUE = CommandDefinition(
        pid=0x15,
        name="zero_adjust_value",
        description="Get/set zero adjustment value",
        read=True,
        write=True,
        param_type=ParamType.UINT16
    )

    DC_OUTPUT_OFFSET = CommandDefinition(
        pid=0x17,
        name="dc_output_offset",
        description="Get/set DC output offset",
        read=True,
        write=True,
        param_type=ParamType.UINT16
    )

    PRODUCTION_NUMBER = CommandDefinition(
        pid=0x19,
        name="production_number",
        description="Read production number",
        read=True,
        write=False
    )

    REMAINING_ZERO = CommandDefinition(
        pid=0x48,
        name="remaining_zero",
        description="Read remaining zero adjustment value",
        read=True,
        write=False
    )

    EXTENDED_ERROR = CommandDefinition(
        pid=0x36,
        name="extended_error",
        description="Read extended error status",
        read=True,
        write=False
    )

    CDG_TYPE = CommandDefinition(
        pid=0x3B,
        name="cdg_type",
        description="Read CDG gauge type",
        read=True,
        write=False
    )

    PRESSURE_RANGE = CommandDefinition(
        pid=0x38,
        name="pressure_range",
        description="Read pressure range configuration",
        read=True,
        write=False
    )

    GAUGE_CONFIG = CommandDefinition(
        pid=0x3A,
        name="gauge_config",
        description="Read gauge configuration",
        read=True,
        write=False
    )

    RESET = CommandDefinition(
        pid=0x00,
        name="reset",
        description="Reset gauge",
        read=False,
        write=True,
        param_type=ParamType.UINT8
    )

    FACTORY_RESET = CommandDefinition(
        pid=0x01,
        name="factory_reset",
        description="Restore factory defaults",
        read=False,
        write=True,
        param_type=ParamType.UINT8
    )
