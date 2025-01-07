# serial_communication/models.py

"""
Defines core data models used throughout the application for both gauges and turbos.
These standardized classes ensure consistent command/response handling across all devices.
"""

from dataclasses import dataclass     # Imports dataclass for convenient data structure creation
from typing import Optional, Dict, Any  # Imports types for better code clarity and type hints

@dataclass
class BaseCommand:
    """
    Provides common attributes for all device commands (gauge or turbo).
    This base class reduces code duplication and standardizes command structure.
    """
    name: str                         # Stores the command's identifier (e.g. 'pressure', 'start_pump')
    command_type: str                 # Indicates command type ('?' for read, '!' for write)
    parameters: Optional[Dict[str, Any]] = None  # Holds optional command parameters
    description: str = ""             # Provides human-readable command description

@dataclass 
class BaseResponse:
    """
    Defines common response attributes for all devices.
    Standardizes how we handle responses across different protocols.
    """
    raw_data: bytes                   # Stores the raw bytes received from device
    formatted_data: str               # Contains human-readable version of response
    success: bool                     # Indicates if command succeeded
    error_message: Optional[str] = None  # Contains error details if command failed

# Creates gauge-specific command and response classes
@dataclass
class GaugeCommand(BaseCommand):
    """
    Extends BaseCommand for vacuum gauge specific attributes.
    Users can add gauge-specific parameters here if needed.
    """
    pass

@dataclass
class GaugeResponse(BaseResponse):
    """
    Extends BaseResponse for vacuum gauge specific attributes.
    Users can add gauge-specific response fields here if needed.
    """
    pass

# Creates turbo-specific command and response classes
@dataclass
class TurboCommand(BaseCommand):
    """
    Extends BaseCommand for turbo pump specific attributes.
    Users can add turbo-specific parameters here if needed.
    """
    pass

@dataclass
class TurboResponse(BaseResponse):
    """
    Extends BaseResponse for turbo pump specific attributes.
    Users can add turbo-specific response fields here if needed.
    """
    pass