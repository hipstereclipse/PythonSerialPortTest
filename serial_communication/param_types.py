"""
Defines parameter types and common command definitions that all gauge protocols can use.
This helps avoid rewriting enumerations or min/max logic in multiple places.
"""

from enum import Enum               # Imports Enum for strongly typed parameters
from dataclasses import dataclass   # Imports dataclass for well-structured data
from typing import Optional, Union


class ParamType(Enum):
    """
    Enumerates all parameter types that can appear in gauge commands:
     - UINT8, UINT16, UINT32 for integer values
     - FLOAT for floating-point values
     - STRING for ASCII text
     - BOOL for True/False parameters
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
    Stores information about a single gauge command:
     - pid: The 'parameter ID' or code used by certain binary protocols.
     - name: A short name for this command (e.g., "pressure").
     - description: A helpful description of what the command does.
     - read: Indicates if this command can read data.
     - write: Indicates if this command can write/adjust data.
     - continuous: Indicates if this command is valid for continuous reading.
     - param_type: Specifies the type of parameter this command uses if it writes.
     - min_value, max_value: (Optional) Constraints for valid parameter values.
     - units: (Optional) Unit of measurement (e.g., "mbar", "°C").
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
