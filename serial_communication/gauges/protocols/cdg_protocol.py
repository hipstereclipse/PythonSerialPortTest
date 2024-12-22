"""
cdg_protocol.py
Implements protocol logic for CDG gauges (Capacitance Diaphragm Gauges) with
automatic model detection logic for "CDGxxxD" families.
"""

from typing import Dict, Any, Optional, List   # Imports types for structured code
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.param_types import ParamType

class CDGProtocol(GaugeProtocol):
    """
    Implements the custom frame structure and logic for CDG gauges.
    Some CDG variants (CDG025D, CDG045D, etc.) share the same basic protocol.
    This class can detect the exact model if gauge_type=CDGxxxD.
    """

    # A dictionary mapping numeric codes in the gauge response to actual models
    CDG_TYPES = {
        0: "CDG025D",
        1: "CDG045D",
        2: "CDG100D",
        3: "CDG160D",
        4: "CDG200D"
    }

    def __init__(self, address: int = 254, logger: Optional[object] = None):
        """
        Initializes the CDGProtocol:
         - Sets an address (default 254, for RS485 if needed).
         - Creates a logger if not provided.
        """
        super().__init__(address, logger)
        # CDG protocol generally doesn't use device IDs, so we set 0x00
        self.device_id = 0x00
        # Flags if strict response validation is on or off
        self._response_validation_enabled = True
        # Tracks the detected specific CDG type (or None if not detected yet)
        self._detected_type = None
        # Tracks the last command name we sent (e.g., "pressure") for context
        self._last_command = None

        self.logger.debug("Initialized generic CDG protocol handler")

    def _initialize_commands(self):
        """
        Loads command definitions from the CDGCommand or from config if we prefer.
        We store them in self._command_defs, which is a dict keyed by command name.
        """
        # Because we do not have a dedicated cdg_commands.py in this snippet,
        # we simply define them inline or we could import them from a separate file.
        self._command_defs = {
            "pressure": {
                "cmd": "read",             # "read" means we read the gauge
                "name": "pressure",
                "desc": "Read pressure"
            },
            "temperature": {
                "cmd": "read",
                "name": "temperature",
                "desc": "Read temperature status"
            },
            "software_version": {
                "cmd": "read",
                "name": "software_version",
                "desc": "Read software version"
            },
            "cdg_type": {
                "cmd": "read",
                "name": "cdg_type",
                "desc": "Read CDG gauge type"
            }
        }

    def test_commands(self) -> List[bytes]:
        """
        Builds and returns a list of raw command frames to test connectivity.
        Typically includes reading the gauge type or a basic page read.
        """
        commands = []

        # Example 1: reading gauge type at address 59
        type_cmd = bytearray([0x03, 0x00, 59, 0x00, 0x00])
        type_cmd[4] = sum(type_cmd[1:4]) & 0xFF
        commands.append(bytes(type_cmd))

        # Example 2: reading page 0
        test_cmd = bytearray([0x03, 0x00, 0x00, 0x00, 0x00])
        test_cmd[4] = sum(test_cmd[1:4]) & 0xFF
        commands.append(bytes(test_cmd))

        return commands

    def detect_gauge_type(self, response: bytes) -> Optional[str]:
        """
        Attempts to interpret the response bytes to discover if it's e.g. CDG025D, CDG045D, etc.
        Only called if gauge_type is "CDGxxxD".
        Returns the found type string (e.g. "CDG045D") or None if unknown.
        """
        # Checks for correct length and known start byte
        if len(response) == 9 and response[0] == 0x07 and self._last_command == "cdg_type":
            # Byte 6 typically indicates the actual model
            cdg_type = response[6]
            return self.CDG_TYPES.get(cdg_type)
        return None

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Creates the 5-byte command frame used by CDG.
        Example structure for read: [ 0x03, 0x00, PID, 0x00, checksum ]
        Example structure for write: [ 0x03, 0x10, PID, valueByte, checksum ]
        """
        # Looks up the command definition
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")

        self._last_command = command.name

        # Builds a minimal 5-byte frame
        msg = bytearray([
            0x03,  # fixed length
            0x00 if command.command_type == "?" else 0x10,  # 0x00 for read, 0x10 for write
            cmd_def["cmd"] if isinstance(cmd_def["cmd"], int) else 0,  # sometimes a pid or address
            0x00  # data byte (for write, if needed)
        ])

        # If the cmd_def["cmd"] is a string like "read", we might interpret it differently
        # In the real code, we might map "read" -> 0x00, "special" -> 0xxx, etc.
        if isinstance(cmd_def["cmd"], str):
            # For demonstration, convert "read" to 0x00, "special" to 0x02, etc.
            if cmd_def["cmd"] == "read":
                msg[2] = 0x00
            elif cmd_def["cmd"] == "special":
                msg[2] = 0x02
            # etc.

        # If we are performing a set command (!), place a value in msg[3]
        if command.command_type == "!":
            if command.parameters:
                value = command.parameters.get("value", 0)
                # Convert the value to an int or something
                msg[3] = self._encode_param(value, ParamType.UINT8)

            # Switch the second byte from 0x00 to 0x10 to indicate write
            msg[1] = 0x10

        # Compute the checksum as sum of bytes [1..3]
        checksum = sum(msg[1:4]) & 0xFF
        msg.append(checksum)

        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Interprets the returned 9-byte frame from a CDG gauge.
        Applies basic validation if enabled, e.g. checking start byte or length.
        """
        try:
            if not response:
                return self._create_error_response("No response received")

            if len(response) != 9:
                return self._create_error_response("Invalid response length")

            if response[0] != 0x07:
                return self._create_error_response("Invalid start byte")

            # If we have strict validation, we can check the checksum
            calc_checksum = sum(response[1:8]) & 0xFF
            if calc_checksum != response[8] and self._response_validation_enabled:
                return self._create_error_response("Checksum mismatch")

            # Possibly detect the gauge type if needed
            if not self._detected_type:
                if self._last_command == "cdg_type":
                    detected = self.detect_gauge_type(response)
                    if detected:
                        self._detected_type = detected
                        self.logger.info(f"Detected CDG gauge type: {detected}")

            # If user asked for "pressure"
            if self._last_command == "pressure":
                pressure = self._calculate_pressure(response[4], response[5])
                status = self._parse_status(response[2])
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=f"Pressure: {pressure:.2e} mbar, Status: {status}",
                    success=True
                )
            elif self._last_command == "temperature":
                # Byte 2 (bits 6) might indicate if temperature is stable
                temp_ok = bool(response[2] & 0x40)
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=f"Temperature {'OK' if temp_ok else 'Not Ready'}",
                    success=True
                )
            elif self._last_command == "cdg_type":
                # Byte 6 holds the gauge type
                type_code = response[6]
                type_str = self.CDG_TYPES.get(type_code, "Unknown")
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=f"CDG Type: {type_str}",
                    success=True
                )

            # Otherwise, just show a hex dump
            return GaugeResponse(
                raw_data=response,
                formatted_data=f"Response: {response.hex(' ').upper()}",
                success=True
            )

        except Exception as e:
            return self._create_error_response(str(e))

    def _calculate_pressure(self, high_byte: int, low_byte: int) -> float:
        """
        Interprets (high_byte, low_byte) as a signed 16-bit integer then divides by 16384.0
        to get the pressure reading in mbar (assuming 14 bits fraction).
        """
        pressure_value = (high_byte << 8) | low_byte
        if pressure_value & 0x8000:
            # Negative number if the sign bit is set
            pressure_value = -((~pressure_value + 1) & 0xFFFF)
        return pressure_value / 16384.0

    def _parse_status(self, status_byte: int) -> Dict[str, Any]:
        """
        Interprets bits in the status byte to see if heating is active, temperature is OK, etc.
        """
        return {
            "heating": bool(status_byte & 0x80),
            "temp_ok": bool(status_byte & 0x40),
            "emission": bool(status_byte & 0x20),
            # Lower nibble can hold unit code (like 0=mbar, 1=Torr, 2=Pa)
            "unit_code": (status_byte >> 4) & 0x03
        }

    def _encode_param(self, value: Any, param_type: ParamType) -> int:
        """
        Encodes a single parameter into a single byte or more, depending on param_type.
        In some designs, we might need more advanced logic. For now, we just do a simple cast.
        """
        if param_type == ParamType.UINT8:
            return int(value) & 0xFF
        return 0

    def _create_error_response(self, message: str) -> GaugeResponse:
        """
        Builds a standardized error response object with a given message.
        """
        self.logger.error(message)
        return GaugeResponse(
            raw_data=b"",
            formatted_data=f"Error: {message}",
            success=False,
            error_message=message
        )
