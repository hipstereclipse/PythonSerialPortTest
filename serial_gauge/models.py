from dataclasses import dataclass
from typing import Optional, Dict, Any
@dataclass
class GaugeCommand:
    name: str
    command_type: str
    parameters: Optional[Dict[str, Any]] = None
    description: str = ""

@dataclass
class GaugeResponse:
    raw_data: bytes
    formatted_data: str
    success: bool
    error_message: Optional[str] = None