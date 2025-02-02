"""
models.py

Defines core data models used throughout the application for both gauges and turbos.
Utilizes dataclasses to enforce structure and type safety.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class BaseCommand:
    """
    Base class for device commands.
    """
    name: str                # Command identifier (e.g., "pressure")
    command_type: str        # "?" for read, "!" for write
    parameters: Optional[Dict[str, Any]] = None  # Optional command parameters
    description: str = ""    # Description of the command


@dataclass
class BaseResponse:
    """
    Base class for device responses.
    """
    raw_data: bytes                  # Raw response bytes
    formatted_data: str              # Human-readable version of the response
    success: bool                    # True if command succeeded
    error_message: Optional[str] = None  # Error message if any


@dataclass
class GaugeCommand(BaseCommand):
    """
    Gauge-specific command (inherits from BaseCommand).
    """
    pass


@dataclass
class GaugeResponse(BaseResponse):
    """
    Gauge-specific response (inherits from BaseResponse).
    """
    pass


@dataclass
class TurboCommand(BaseCommand):
    """
    Turbo-specific command (inherits from BaseCommand).
    """
    pass


@dataclass
class TurboResponse(BaseResponse):
    """
    Turbo-specific response (inherits from BaseResponse).
    """
    pass
