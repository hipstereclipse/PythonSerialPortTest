"""
param_types.py

Defines parameter types for gauge commands and a dataclass for command definitions.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Union


class ParamType(Enum):
    """
    Enumeration for parameter types.
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
    Data class for storing command definitions.
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
