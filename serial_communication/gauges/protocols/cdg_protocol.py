"""
Implements protocol logic for CDG gauges with automatic model detection.
"""

from typing import Dict, Any, Optional, List

from serial_communication.gauges.commands.cdg_commands import CDGCommand
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.param_types import ParamType

class CDGProtocol(GaugeProtocol):
    """
    Implements the custom frame structure and logic for CDG gauges.
    Includes automatic model detection.
    """

    CDG_TYPES = {
        0: "CDG025D",
        1: "CDG045D",
        2: "CDG100D",
        3: "CDG160D",
        4: "CDG200D"
    }

    def __init__(self, address: int = 254, logger: Optional[object] = None):
        super().__init__(address, logger)
        self.device_id = 0x00  # CDG protocol doesn't use device ID
        self._response_validation_enabled = True
        self._detected_type = None
        self._last_command = None
        self.logger.debug(f"Initialized generic CDG protocol handler")

    def _initialize_commands(self):
        """Initialize commands from CDGCommand class."""
        for cmd in vars(CDGCommand).values():
            if isinstance(cmd, dict) or hasattr(cmd, 'pid'):
                self._command_defs[cmd.name] = cmd

    def test_commands(self) -> List[bytes]:
        """Returns test commands to verify connectivity and detect gauge type."""
        commands = []

        # Command to read CDG type (Address 59)
        type_cmd = bytearray([0x03, 0x00, 59, 0x00, 0x00])
        type_cmd[4] = sum(type_cmd[1:4]) & 0xFF
        commands.append(bytes(type_cmd))

        # Command to read page 0 (standard test)
        test_cmd = bytearray([0x03, 0x00, 0x00, 0x00, 0x00])
        test_cmd[4] = sum(test_cmd[1:4]) & 0xFF
        commands.append(bytes(test_cmd))

        return commands

    def detect_gauge_type(self, response: bytes) -> Optional[str]:
        """
           Detect the CDG gauge type from a response to the 'cdg_type' command.
           Returns the detected type or None if detection failed.
        """
        if len(response) == 9 and response[0] == 0x07 and self._last_command == "cdg_type":
            cdg_type = response[6]  # Byte 6 contains the gauge type.
            return self.CDG_TYPES.get(cdg_type)
        return None

    def create_command(self, command: GaugeCommand) -> bytes:
        """Creates a properly formatted 5-byte command frame."""
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")

        self._last_command = command.name

        # Basic command structure
        msg = bytearray([
            0x03,  # Fixed length
            0x00 if command.command_type == "?" else 0x10,  # Read/Write
            cmd_def.pid & 0xFF,  # Command/Address byte
            0x00  # Data byte (used for write commands)
        ])

        # Handle write commands with parameters
        if command.command_type == "!" and command.parameters:
            value = command.parameters.get('value', 0)
            msg[3] = self._encode_param(value, cmd_def.param_type)

        # Calculate checksum
        msg.append(sum(msg[1:4]) & 0xFF)

        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Parses CDG gauge response and handles automatic type detection.
        """
        try:
            if not response:
                return self._create_error_response("No response received")

            if len(response) != 9:
                return self._create_error_response("Invalid response length")

            if response[0] != 0x07:
                return self._create_error_response("Invalid start byte")

            # Check response checksum
            calc_checksum = sum(response[1:8]) & 0xFF
            if calc_checksum != response[8]:
                return self._create_error_response("Checksum mismatch")

            # Try to detect gauge type if not already detected
            if not self._detected_type:
                detected = self.detect_gauge_type(response)
                if detected:
                    self._detected_type = detected
                    self.logger.info(f"Detected CDG gauge type: {detected}")

            # Parse the response based on command type
            if self._last_command == "pressure":
                pressure = self._calculate_pressure(response[4], response[5])
                status = self._parse_status(response[2])
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=f"Pressure: {pressure:.2e} mbar, Status: {status}",
                    success=True
                )
            elif self._last_command == "temperature":
                temp_ok = bool(response[2] & 0x40)
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=f"Temperature {'OK' if temp_ok else 'Not Ready'}",
                    success=True
                )
            elif self._last_command == "cdg_type":
                cdg_type = response[6]
                type_str = self.CDG_TYPES.get(cdg_type, "Unknown")
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=f"CDG Type: {type_str}",
                    success=True
                )

            # Default response handling
            return GaugeResponse(
                raw_data=response,
                formatted_data=f"Response: {response.hex(' ').upper()}",
                success=True
            )

        except Exception as e:
            return self._create_error_response(str(e))

    def _calculate_pressure(self, high_byte: int, low_byte: int) -> float:
        """Calculates pressure from the gauge's response bytes."""
        pressure_value = (high_byte << 8) | low_byte
        if pressure_value & 0x8000:
            pressure_value = -((~pressure_value + 1) & 0xFFFF)
        return pressure_value / 16384.0

    def _parse_status(self, status_byte: int) -> Dict[str, Any]:
        """Parses the status byte from the gauge response."""
        return {
            "heating": bool(status_byte & 0x80),
            "temp_ok": bool(status_byte & 0x40),
            "emission": bool(status_byte & 0x20),
            "unit": ["mbar", "Torr", "Pa"][(status_byte >> 4) & 0x03],
        }

    def _encode_param(self, value: Any, param_type: ParamType) -> int:
        """Encodes a parameter value for write commands."""
        if param_type == ParamType.UINT8:
            return int(value) & 0xFF
        elif param_type == ParamType.UINT16:
            return int(value) & 0xFFFF
        elif param_type == ParamType.FLOAT:
            return int(value * 16384.0) & 0xFFFF
        return 0

    def _create_error_response(self, message: str) -> GaugeResponse:
        """Creates a standardized error response."""
        self.logger.error(message)
        return GaugeResponse(
            raw_data=b"",
            formatted_data=f"Error: {message}",
            success=False,
            error_message=message
        )