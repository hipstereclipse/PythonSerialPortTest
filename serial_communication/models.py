"""
Defines data models (GaugeCommand, GaugeResponse) used throughout the application.
They store information about commands sent and responses received.
"""

from dataclasses import dataclass     # Imports dataclass for convenient data structure
from typing import Optional, Dict, Any  # Imports types for better code clarity


@dataclass
class GaugeCommand:
    """
    Holds information about a single gauge command.
     - name: The command's textual identifier (e.g., 'pressure', 'zero_adjust').
     - command_type: Typically '?' for read, '!' for write, or can be used by specific protocols.
     - parameters: Any additional data to send with the command (e.g., setpoints, addresses).
     - description: An optional field to describe the command usage.
    """
    name: str
    command_type: str
    parameters: Optional[Dict[str, Any]] = None
    description: str = ""


@dataclass
class GaugeResponse:
    """
    Represents a response from the gauge.
     - raw_data: The raw bytes received from the gauge.
     - formatted_data: A user-friendly string representation of the data.
     - success: Indicates if the gauge responded successfully.
     - error_message: Contains any error or exception info if not successful.
    """
    raw_data: bytes
    formatted_data: str
    success: bool
    error_message: Optional[str] = None
