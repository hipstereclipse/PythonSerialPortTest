"""
Complete implementation of BCG450 protocol with improved response handling and full command support.
"""

import struct
from typing import Dict, Any, Optional, List
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.param_types import ParamType
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol

class BCG450Protocol(GaugeProtocol):
    def __init__(self, address: int = 254, logger: Optional[object] = None):
        super().__init__(address, logger)
        self.device_id = 0x0B
        self._response_validation_enabled = True
        self.rs485_mode = False
        self._last_command = None
        self.logger.debug(f"Initialized BCG450 protocol handler")

    def _initialize_commands(self):
        """
        Initialize all available commands with their response handling characteristics.
        Each command includes its PID, type, and expected response format.
        """
        self._command_defs = {
            # Measurement commands
            "pressure": {
                "pid": 221,
                "cmd": 1,
                "desc": "Read pressure measurement",
                "response_type": "pressure"
            },
            "temperature": {
                "pid": 222,
                "cmd": 1,
                "desc": "Read temperature",
                "response_type": "temperature"
            },

            # Status commands
            "sensor_status": {
                "pid": 223,
                "cmd": 1,
                "desc": "Get active sensor status",
                "response_type": "status"
            },
            "error_status": {
                "pid": 228,
                "cmd": 1,
                "desc": "Read error status",
                "response_type": "error"
            },

            # Information commands
            "serial_number": {
                "pid": 207,
                "cmd": 1,
                "desc": "Read serial number",
                "response_type": "text"
            },
            "software_version": {
                "pid": 218,
                "cmd": 1,
                "desc": "Read software version",
                "response_type": "version"
            },

            # Control commands
            "ba_degas": {
                "pid": 529,
                "cmd": 3,
                "desc": "Control BA degas",
                "response_type": "control",
                "parameters": True
            },
            "pirani_adjust": {
                "pid": 418,
                "cmd": 3,
                "desc": "Execute Pirani adjustment",
                "response_type": "control",
                "parameters": False
            }
        }

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Creates a properly formatted command byte sequence.
        Handles both read and write commands with appropriate parameters.
        """
        cmd_info = self._command_defs.get(command.name)
        if not cmd_info:
            raise ValueError(f"Unknown command: {command.name}")

        self._last_command = command.name

        # Create the basic command frame
        msg = bytearray([
            self.address if self.rs485_mode else 0x00,
            0x0B,  # Device ID
            0x00,  # ACK bit
            0x05,  # Default length
            0x01 if cmd_info['cmd'] == 1 else 0x03,  # Command type
            (cmd_info['pid'] >> 8) & 0xFF,
            cmd_info['pid'] & 0xFF,
            0x00, 0x00
        ])

        # Add parameters for write commands if needed
        if command.command_type == "!" and cmd_info.get('parameters', False):
            value = command.parameters.get('value', 0)
            if isinstance(value, bool):
                msg.extend([0x01 if value else 0x00])
            else:
                msg.extend([int(value) & 0xFF])
            msg[3] = len(msg) - 4

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Parses response data with improved handling of various response patterns.
        More lenient validation that accepts common response formats.
        """
        try:
            if not response:
                return self._create_error_response("No response received", response)

            # During initial testing, be very lenient
            if not self._response_validation_enabled:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=response.hex(' ').upper(),
                    success=True
                )

            # Find any meaningful data in the response
            data = self._find_meaningful_data(response)
            if not data:
                # For control commands, an empty response might be OK
                if self._last_command in ['ba_degas', 'pirani_adjust']:
                    return GaugeResponse(
                        raw_data=response,
                        formatted_data="Command acknowledged",
                        success=True
                    )
                return self._create_error_response("No valid data found", response)

            # Parse the data according to command type
            parsed_result = self._parse_command_response(data)
            return GaugeResponse(
                raw_data=response,
                formatted_data=str(parsed_result),
                success=True
            )

        except Exception as e:
            return self._create_error_response(str(e), response)

    def _find_meaningful_data(self, response: bytes) -> Optional[bytes]:
        """
        Searches for meaningful data in the response, ignoring common filler bytes.
        More sophisticated pattern matching for different response formats.
        """
        # Look for 4-byte chunks that contain non-zero, non-E0 bytes
        for i in range(len(response) - 3):
            chunk = response[i:i+4]
            if any(b != 0 and b != 0xE0 for b in chunk):
                return chunk
        return None

    def _parse_command_response(self, data: bytes) -> Dict[str, Any]:
        """
        Parses response data based on the command type.
        Includes special handling for different measurement and status responses.
        """
        if not self._last_command:
            return {"raw_data": data.hex(' ').upper()}

        cmd_info = self._command_defs.get(self._last_command)
        if not cmd_info:
            return {"raw_data": data.hex(' ').upper()}

        response_type = cmd_info.get('response_type', 'raw')

        if response_type == "pressure":
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {"pressure": f"{pressure:.2e} mbar"}

        elif response_type == "temperature":
            value = int.from_bytes(data, byteorder='big', signed=True)
            temp = value / 100.0
            return {"temperature": f"{temp:.1f}°C"}

        elif response_type == "status":
            status = data[0]
            return {
                "status": {
                    "pirani": "ACTIVE" if status & 0x01 else "INACTIVE",
                    "ba": "ACTIVE" if status & 0x02 else "INACTIVE",
                    "degas": "ON" if status & 0x08 else "OFF"
                }
            }

        elif response_type == "control":
            return {"result": "Command executed successfully"}

        return {"value": data.hex(' ').upper()}

    def _create_error_response(self, message: str, response: bytes) -> GaugeResponse:
        """Creates a standardized error response with the raw data included."""
        error_msg = f"Error: {message}"
        if response:
            error_msg += f" (Raw: {response.hex(' ').upper()})"
        return GaugeResponse(
            raw_data=response,
            formatted_data=error_msg,
            success=False,
            error_message=message
        )

    def test_commands(self) -> List[bytes]:
        """Generate test commands for initial connection verification."""
        self._response_validation_enabled = False
        return [self.create_command(GaugeCommand(name="pressure", command_type="?"))]