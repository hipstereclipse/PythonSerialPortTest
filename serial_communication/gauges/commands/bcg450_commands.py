"""
Defines command definitions for BCG450 combination gauges.
"""

from serial_communication.param_types import CommandDefinition, ParamType

class BCG450Command:
    """
    Holds command definitions for BCG450 combination gauges.
    """
    PRESSURE = CommandDefinition(
        pid=221,
        name="pressure",
        description="Read pressure measurement",
        read=True,
        write=False,
        continuous=True
    )
    SENSOR_STATUS = CommandDefinition(
        pid=223,
        name="sensor_status",
        description="Get active sensor status",
        read=True,
        write=False
    )
    PIRANI_ADJ = CommandDefinition(
        pid=418,
        name="pirani_adjust",
        description="Adjust Pirani sensor",
        read=False,
        write=True
    )
    BA_DEGAS = CommandDefinition(
        pid=529,
        name="ba_degas",
        description="Control BA degas",
        read=False,
        write=True
    )
