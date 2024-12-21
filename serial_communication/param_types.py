"""
Defines parameter types and common command definitions that all gauge protocols can use.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Union

class ParamType(Enum):
    """
    Declares all parameter types that can be used by gauge commands.
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
    Stores information about a single gauge command.
    Includes properties such as its ID, name, description, and parameter constraints.
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
