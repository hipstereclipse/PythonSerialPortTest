"""
tc600_commands.py

Defines the TC600Command data class for the TC600 turbo pump controller.
Each instance represents a command/parameter used by the TC600.

Usage Example:
    cmd = TC600Command(number=TC600CommandType.ROTATION_SPEED.value,
                       name="get_speed",
                       description="Read the current rotation speed in rpm",
                       data_type="u_integer",
                       read=True)
"""

from enum import Enum
from dataclasses import dataclass

class TC600CommandType(Enum):
    """
    Enumerates known parameter numbers (PIDs) for the TC600 pump controller.
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
    Represents a command for the TC600 pump controller.

    Attributes:
        number: The parameter number (PID) for the command.
        name: A short, descriptive name for the command.
        description: A detailed description of the command.
        data_type: The expected data type for this command's value (e.g., "u_integer", "string").
        read: True if the command is a read command.
        write: True if the command supports writing a new value.
    """
    number: int
    name: str
    description: str
    data_type: str
    read: bool = True
    write: bool = False
