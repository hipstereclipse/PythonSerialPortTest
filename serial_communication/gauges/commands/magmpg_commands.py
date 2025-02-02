"""
magmpg_commands.py

Defines command definitions for MAG500 and MPG500 combination gauges.
These definitions differ slightly between the two models.
"""

from serial_communication.param_types import CommandDefinition

class MAG500Command:
    """
    Command definitions specific to the MAG500 cold cathode gauge.
    """
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure (LogFixs32en26)", True, False, True)
    TEMPERATURE = CommandDefinition(222, "temperature", "Read temperature", True, False)
    SERIAL_NUMBER = CommandDefinition(207, "serial_number", "Read serial number", True, False)
    SOFTWARE_VERSION = CommandDefinition(218, "software_version", "Read software version", True, False)
    ERROR_STATUS = CommandDefinition(228, "device_exception", "Read device errors", True, False)
    RUN_HOURS = CommandDefinition(104, "run_hours", "Read operating hours", True, False)
    CCIG_STATUS = CommandDefinition(533, "ccig_status", "CCIG status (0=off, 1=on not ignited, 3=on and ignited)", True, False)
    CCIG_CONTROL = CommandDefinition(529, "ccig_control", "Switch CCIG on/off", False, True)
    CCIG_FULL_SCALE = CommandDefinition(503, "ccig_full_scale", "Read CCIG full scale", True, False)
    CCIG_SAFE_STATE = CommandDefinition(504, "ccig_safe_state", "Read CCIG safe state", True, False)

class MPG500Command:
    """
    Command definitions specific to the MPG500 combination gauge.
    """
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure (LogFixs32en26)", True, False, True)
    TEMPERATURE = CommandDefinition(222, "temperature", "Read temperature", True, False)
    SERIAL_NUMBER = CommandDefinition(207, "serial_number", "Read serial number", True, False)
    SOFTWARE_VERSION = CommandDefinition(218, "software_version", "Read software version", True, False)
    ERROR_STATUS = CommandDefinition(228, "device_exception", "Read device errors", True, False)
    RUN_HOURS = CommandDefinition(104, "run_hours", "Read operating hours", True, False)
    ACTIVE_SENSOR = CommandDefinition(223, "active_sensor", "Current active sensor (1=CCIG, 2=Pirani, 3=Mixed)", True, False)
    PIRANI_FULL_SCALE = CommandDefinition(33000, "pirani_full_scale", "Read Pirani full scale", True, False)
    PIRANI_ADJUST = CommandDefinition(418, "pirani_adjust", "Execute Pirani adjustment", False, True)
