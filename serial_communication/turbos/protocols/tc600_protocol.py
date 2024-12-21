"""
Implements protocol logic for the TC600 turbopump controller.
"""

from typing import Dict, Any, Optional, List, Tuple

from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand, GaugeResponse


class TC600Protocol(GaugeProtocol):
    """
    Handles reading and writing of parameters for the TC600 pump controller
    using ASCII-based commands with checksums.
    """

    def __init__(self, address: int = 1, logger: Optional[object] = None):
        super().__init__(address, logger)
        self.device_type = "TC600"
        self.current_command = None

    def _initialize_commands(self):
        # Example dictionary of command definitions.
        # Expand or adjust for full coverage.
        self._command_defs = {
            "motor_on": {
                "pid": 23,
                "desc": "Switch motor/pump on/off",
                "type": "boolean_old",
                "write": True,
                "options": ["0", "1"],
                "option_desc": ["Off", "On"]
            },
            "get_speed": {
                "pid": 309,
                "desc": "Get actual rotation speed (rpm)",
                "type": "u_integer"
            },
            "set_speed": {
                "pid": 308,
                "desc": "Set rotation speed (percentage of nominal)",
                "type": "u_integer",
                "write": True,
                "min": 0,
                "max": 100,
                "unit": "%",
                "format": "percentage"
            },
            "get_error": {
                "pid": 303,
                "desc": "Get current error code",
                "type": "u_integer"
            },
        }

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Builds ASCII-based message for the TC600.
        """
        if command.name not in self._command_defs:
            raise ValueError(f"Unknown command: {command.name}")

        cmd_info = self._command_defs[command.name]
        self.current_command = command.name

        addr = f"{self.address:03d}"
        action = "10" if command.command_type == "!" else "00"
        param = f"{cmd_info['pid']:03d}"

        if command.command_type == "!":
            value = command.parameters.get('value', 0)
            data_bytes = self._encode_value(value, cmd_info.get('type'))
            data_len = f"{len(data_bytes):02d}"
            msg = f"{addr}{action}{param}{data_len}{data_bytes}"
        else:
            # For reads, we use 02=? as data indicator
            msg = f"{addr}{action}{param}02=?"

        checksum = sum(msg.encode('ascii')) % 256
        msg = f"{msg}{checksum:03d}\r"
        return msg.encode('ascii')

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Interprets ASCII response from the TC600 and checks for error codes.
        """
        try:
            resp_str = response.decode('ascii').strip()

            if len(resp_str) < 10:
                return GaugeResponse(response, "", False, "Response too short")

            # Example decoding logic
            addr = resp_str[0:3]
            action = resp_str[3:5]
            param = resp_str[5:8]
            data = resp_str[10:-4] if len(resp_str) > 12 else ""

            if "NO_DEF" in resp_str:
                return GaugeResponse(response, "Parameter does not exist", False, "Invalid parameter")
            if "_RANGE" in resp_str:
                return GaugeResponse(response, "Value out of range", False, "Value out of valid range")
            if "_LOGIC" in resp_str:
                return GaugeResponse(response, "Logic error", False, "Command logic error")

            return GaugeResponse(
                raw_data=response,
                formatted_data=self._format_response_data(data),
                success=True
            )

        except Exception as e:
            return GaugeResponse(response, "", False, f"Parse error: {str(e)}")

    def _encode_value(self, value: Any, data_type: str) -> str:
        """
        Converts the parameter value into the 6-digit ASCII form used by TC600.
        """
        if data_type == "boolean_old":
            return "111111" if value else "000000"
        elif data_type == "u_integer":
            return f"{int(value):06d}"
        elif data_type == "u_real":
            fixed = int(float(value) * 100)
            return f"{fixed:06d}"
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _format_response_data(self, data: str) -> str:
        """
        Converts the raw ASCII data from the gauge into a more readable form.
        """
        if not data or data.isspace():
            return "No data"

        # Example logic to detect boolean_old
        if len(data) == 6 and all(c in "01" for c in data):
            return "On" if data == "111111" else "Off"
        elif data.isdigit() and self.current_command == "get_speed":
            return f"{int(data)} RPM"

        return data
