"""
Implements protocol logic and commands for TC600 turbopump controller.
Handles all available parameters and commands from TC600 documentation.
"""

from typing import Dict, Any, Optional, List, Tuple
import struct

from serial_communication.turbos.protocols.turbo_protocol import TurboProtocol
from serial_communication.models import TurboCommand, TurboResponse

class TC600Protocol(TurboProtocol):
    """
    Handles TC600 pump controller protocol.
    Implements all available parameters and commands according to TC600 specifications.
    """

    def __init__(self, address: int = 1, logger: Optional[object] = None):
        """Creates protocol handler with device ID and logger"""
        super().__init__(address, logger)
        self.device_type = "TC600"
        self.current_command = None

    def _initialize_commands(self):
        """
        Initializes the dictionary of TC600 command definitions.
        Each dictionary key is the command name you will use externally (e.g., "read_speed").
        Each value is another dictionary containing parameters like:
          - pid      : The parameter ID in the device's protocol
          - desc     : A short description of what this command does
          - type     : The data type expected (e.g., "u_integer", "u_real", "boolean_old", or "string")
          - write    : A boolean indicating if this command supports writing (True) or read-only (False)
          - options  : (Optional) A list of allowed string values if you want enumerated choices
          - min, max : (Optional) Numeric limits if the command takes an integer or float
          - unit     : (Optional) A string describing the unit (e.g., "A" for amps, "°C" for Celsius)
        """

        # Creates a dictionary to store all TC600 commands
        self._command_defs = {

            # Reads the current rotation speed in rpm
            "get_speed": {
                "pid": 309,  # Uses PID 309 (from device docs) to read the speed
                "desc": "Read turbo rotation speed (rpm)",
                "type": "u_integer"  # 'u_integer' means an unsigned integer
            },

            # Sets the rotation speed (as a percentage of maximum)
            "set_speed": {
                "pid": 308,  # Device docs say PID 308 sets speed
                "desc": "Set the turbo rotation speed (percent of max)",
                "type": "u_integer",  # Expects an integer
                "write": True,  # Because we can write to it
                "min": 0,  # 0% speed means off
                "max": 100,  # 100% means full speed
                "unit": "%"  # Just labeling that the value is in percent
            },

            # Reads the motor current (in amps)
            "get_current": {
                "pid": 310,
                "desc": "Read motor current (A)",
                "type": "u_real",  # 'u_real' means an unsigned real number
                "unit": "A"  # Amps
            },

            # Turns the motor on/off (boolean style command)
            "motor_on": {
                "pid": 23,
                "desc": "Switch motor/pump on or off",
                "type": "boolean_old",  # 'boolean_old' is a custom format (like '111111' for On, '000000' for Off)
                "write": True,  # We can write to toggle on/off
                "options": ["0", "1"],  # If you prefer to interpret 0/1
                "option_desc": ["Off", "On"]
            },

            # Reads the electronics temperature in °C
            "get_temp_electronic": {
                "pid": 326,
                "desc": "Read electronics temperature (°C)",
                "type": "u_integer",
                "unit": "°C"
            },

            # Reads the motor temperature in °C
            "get_temp_motor": {
                "pid": 330,
                "desc": "Read motor temperature (°C)",
                "type": "u_integer",
                "unit": "°C"
            },

            # Reads the bearing temperature in °C
            "get_temp_bearing": {
                "pid": 342,
                "desc": "Read bearing temperature (°C)",
                "type": "u_integer",
                "unit": "°C"
            },

            # Reads any current error codes from the pump
            "get_error": {
                "pid": 303,
                "desc": "Read current error code",
                "type": "u_integer"
            },

            # Reads any current warnings or non-critical notices
            "get_warning": {
                "pid": 305,
                "desc": "Read current warning status",
                "type": "u_integer"
            },

            # Reads total operating hours on the pump
            "operating_hours": {
                "pid": 311,
                "desc": "Read total operating hours",
                "type": "u_integer"
            },

            # Sets maximum run-up time (in seconds)
            "set_runup_time": {
                "pid": 700,
                "desc": "Set maximum run-up time before reaching nominal speed",
                "type": "u_integer",
                "write": True,
                "unit": "sec",
                "min": 1,
                "max": 1200
            },

            # Controls venting valve mode (closed, controlled, or open)
            "vent_mode": {
                "pid": 30,
                "desc": "Set venting valve mode",
                "type": "u_integer",
                "write": True,
                "options": ["0", "1", "2"],
                "option_desc": ["Closed", "Controlled", "Open"]
            },

            # Sets venting time (in seconds)
            "vent_time": {
                "pid": 721,
                "desc": "Set venting duration (seconds)",
                "type": "u_integer",
                "write": True,
                "unit": "sec",
                "min": 1,
                "max": 3600
            },

            # Reads the firmware version string
            "firmware_version": {
                "pid": 312,
                "desc": "Read firmware version string",
                "type": "string"
            },

            # Reads the pump type (e.g. "TC600", "TC1200")
            "pump_type": {
                "pid": 369,
                "desc": "Read pump type",
                "type": "string"
            },

            # Allows changing the station address (1..255) for RS485
            "station_number": {
                "pid": 797,
                "desc": "Set station number/address",
                "type": "u_integer",
                "write": True,
                "min": 1,
                "max": 255
            },

            # Allows changing the baud rate (e.g., 9600, 19200, 38400)
            "baud_rate": {
                "pid": 798,
                "desc": "Set communication baud rate",
                "type": "u_integer",
                "write": True,
                "options": ["9600", "19200", "38400"],
                "option_desc": ["9600 baud", "19200 baud", "38400 baud"]
            },

            # Lets you switch between RS232 or RS485
            "interface_type": {
                "pid": 794,
                "desc": "Set interface type (RS232 or RS485)",
                "type": "u_integer",
                "write": True,
                "options": ["0", "1"],
                "option_desc": ["RS232", "RS485"]
            }
        }

    def create_command(self, command: TurboCommand) -> bytes:
        """
        Creates properly formatted TC600 command string.
        Handles both read and write commands with checksums.
        """
        # Validates command exists
        if command.name not in self._command_defs:
            raise ValueError(f"Unknown command: {command.name}")

        # Gets command definition
        cmd_info = self._command_defs[command.name]
        self.current_command = command.name

        # Formats address and parameter info
        addr = f"{self.address:03d}"
        action = "10" if command.command_type == "!" else "00"
        param = f"{cmd_info['pid']:03d}"

        # Creates command string
        if command.command_type == "!":
            # Write command with parameter
            value = command.parameters.get('value', 0)
            data_bytes = self._encode_value(value, cmd_info.get('type'))
            data_len = f"{len(data_bytes):02d}"
            msg = f"{addr}{action}{param}{data_len}{data_bytes}"
        else:
            # Read command
            msg = f"{addr}{action}{param}02=?"

        # Adds checksum and terminator
        checksum = sum(msg.encode('ascii')) % 256
        msg = f"{msg}{checksum:03d}\r"

        return msg.encode('ascii')

    def parse_response(self, response: bytes) -> TurboResponse:
        """
        Parses TC600 response and handles error conditions.
        Formats response data based on command type.
        """
        try:
            # Decodes ASCII response
            resp_str = response.decode('ascii').strip()

            if len(resp_str) < 10:
                return TurboResponse(response, "", False, "Response too short")

            # Extracts response components
            addr = resp_str[0:3]
            action = resp_str[3:5]
            param = resp_str[5:8]
            data = resp_str[10:-4] if len(resp_str) > 12 else ""

            # Handles error responses
            if "NO_DEF" in resp_str:
                return TurboResponse(response, "Parameter does not exist", False, "Invalid parameter")
            if "_RANGE" in resp_str:
                return TurboResponse(response, "Value out of range", False, "Value out of valid range")
            if "_LOGIC" in resp_str:
                return TurboResponse(response, "Logic error", False, "Command logic error")

            # Formats successful response
            return TurboResponse(
                raw_data=response,
                formatted_data=self._format_response_data(data),
                success=True
            )

        except Exception as e:
            return TurboResponse(response, "", False, f"Parse error: {str(e)}")

    def _encode_value(self, value: Any, data_type: str) -> str:
        """
        Converts parameter values to TC600 format.
        Handles all supported data types.
        """
        if data_type == "boolean_old":
            return "111111" if value else "000000"
        elif data_type == "u_integer":
            return f"{int(value):06d}"
        elif data_type == "u_real":
            fixed = int(float(value) * 100)
            return f"{fixed:06d}"
        elif data_type == "string":
            return str(value)[:6].ljust(6)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _format_response_data(self, data: str) -> str:
        """
        Formats response data based on command type.
        Adds units and proper formatting for each type.
        """
        if not data or data.isspace():
            return "No data"

        # Gets command info for formatting
        cmd_info = self._command_defs.get(self.current_command, {})

        # Handles boolean values
        if len(data) == 6 and all(c in "01" for c in data):
            return "On" if data == "111111" else "Off"

        # Formats numeric values with units
        if cmd_info.get('type') in ['u_integer', 'u_real']:
            try:
                value = int(data)
                if self.current_command == "get_speed":
                    return f"{value} RPM"
                elif 'unit' in cmd_info:
                    return f"{value} {cmd_info['unit']}"
                return str(value)
            except ValueError:
                pass

        # Returns raw string for other types
        return data

    def test_commands(self) -> List[bytes]:
        """
        Generates test commands for verifying connection.
        Uses non-destructive read commands.
        """
        return [
            self.create_command(TurboCommand(name="get_speed", command_type="?")),
            self.create_command(TurboCommand(name="get_error", command_type="?"))
        ]