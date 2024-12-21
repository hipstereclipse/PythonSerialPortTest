"""
Defines command definitions for TC600 turbopump controller.
"""

from enum import Enum
from dataclasses import dataclass

class TC600CommandType(Enum):
    """
    Shows some known parameter numbers for the TC600 pump controller.
    These might differ from the actual device documentation.
    """
    MOTOR_PUMP = 23
    ROTATION_SPEED = 309
    SET_ROTATION = 308
    DRIVE_CURRENT = 310
    TEMP_ELECTRONIC = 326
    TEMP_MOTOR = 330
    TEMP_PUMP = 342
    OPERATING_HOURS = 311
    POWER_CONSUMPTION = 316
    ERROR_CODE = 303
    WARNING_CODE = 305
    STATION_NUMBER = 797
    BAUD_RATE = 798
    INTERFACE_TYPE = 794
    FIRMWARE_VERSION = 312
    PUMP_TYPE = 369
    RUN_UP_TIME = 700
    VENT_MODE = 30
    GAS_MODE = 27
    SEALING_GAS = 31
    STANDBY_SPEED = 707

@dataclass
class TC600Command:
    """
    Defines a command or parameter for the TC600 with the parameter number, name, etc.
    Used to create the param dictionary in the protocol.
    """
    number: int
    name: str
    description: str
    data_type: str
    read: bool = True
    write: bool = False
