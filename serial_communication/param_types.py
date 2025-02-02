"""
param_types.py

Defines parameter types and a data class for command definitions.
This file standardizes the types of parameters used across all gauge commands.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Union

class ParamType(Enum):
    """
    Enumeration of parameter types used in gauge commands.
    """
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"

@dataclass
class CommandDefinition:
    """
    Data class representing a command definition for a gauge.

    Attributes:
        pid: The parameter ID (PID) used in binary protocols.
        name: A short name for the command.
        description: A human-readable description of what the command does.
        read: True if the command is a read command.
        write: True if the command is writable.
        continuous: True if the command can be used in continuous reading mode.
        param_type: The type of parameter (if any) this command accepts.
        min_value: The minimum allowed value (if applicable).
        max_value: The maximum allowed value (if applicable).
        units: A string representing the unit of measure (e.g., "mbar", "°C").
    """
    pid: int
    name: str
    description: str
    read: bool = False
    write: bool = False
    continuous: bool = False
    param_type: Optional[ParamType] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    units: Optional[str] = None
