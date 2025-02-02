"""
tc600_commands.py

Defines the TC600Command data class for the TC600 turbo pump controller.
Each instance represents a command/parameter for the TC600.
"""

from enum import Enum
from dataclasses import dataclass

class TC600CommandType(Enum):
    """
    Enumerates known TC600 command parameter numbers.
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
    Represents a command for the TC600 pump.

    Attributes:
        number: The parameter number (PID).
        name: A short name for the command.
        description: A description of the command.
        data_type: The type of data (e.g., "u_integer", "string").
        read: True if the command is readable.
        write: True if the command is writable.
    """
    number: int
    name: str
    description: str
    data_type: str
    read: bool = True
    write: bool = False
