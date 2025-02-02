#!/usr/bin/env python3
"""
tc600_protocol.py

Implements the protocol for the TC600 turbo pump controller.
Handles command creation, parameter encoding, response parsing, and error handling.
Commands are formatted as ASCII strings with a checksum and terminator.
"""

import struct
from typing import Dict, Any, Optional, List
import logging

from serial_communication.turbos.protocols.turbo_protocol import TurboProtocol
from serial_communication.models import TurboCommand, TurboResponse

class TC600Protocol(TurboProtocol):
    """
    Protocol implementation for the TC600 pump controller.
    """

    def __init__(self, address: int = 1, logger: Optional[Any] = None):
        """
        Initializes the TC600Protocol.

        Args:
            address (int): The device address (default: 1).
            logger (Optional[Any]): Logger instance.
        """
        super().__init__(address, logger)
        self.device_type = "TC600"
        self.current_command = None

    def _initialize_commands(self) -> None:
        """
        Initializes a dictionary of TC600 command definitions.
        Each definition includes the parameter ID (pid), a description, data type, and flags for read/write.
        """
        self._command_defs = {
            "get_speed": {
                "pid": 309,
                "desc": "Read turbo rotation speed (rpm)",
                "type": "u_integer"
            },
            "set_speed": {
                "pid": 308,
                "desc": "Set turbo rotation speed (percent of max)",
                "type": "u_integer",
                "write": True,
                "min": 0,
                "max": 100,
                "unit": "%"
            },
            "get_current": {
                "pid": 310,
                "desc": "Read motor current (A)",
                "type": "u_real",
                "unit": "A"
            },
            "motor_on": {
                "pid": 23,
                "desc": "Switch pump motor on/off",
                "type": "boolean_old",
                "write": True,
                "options": ["0", "1"],
                "option_desc": ["Off", "On"]
            },
            "get_temp_electronic": {
                "pid": 326,
                "desc": "Read electronics temperature (°C)",
                "type": "u_integer",
                "unit": "°C"
            },
            "get_temp_motor": {
                "pid": 330,
                "desc": "Read motor temperature (°C)",
                "type": "u_integer",
                "unit": "°C"
            },
            "get_temp_bearing": {
                "pid": 342,
                "desc": "Read bearing temperature (°C)",
                "type": "u_integer",
                "unit": "°C"
            },
            "get_error": {
                "pid": 303,
                "desc": "Read error code",
                "type": "u_integer"
            },
            "get_warning": {
                "pid": 305,
                "desc": "Read warning status",
                "type": "u_integer"
            },
            "operating_hours": {
                "pid": 311,
                "desc": "Read operating hours",
                "type": "u_integer"
            },
            "set_runup_time": {
                "pid": 700,
                "desc": "Set maximum run-up time before reaching nominal speed",
                "type": "u_integer",
                "write": True,
                "unit": "sec",
                "min": 1,
                "max": 1200
            },
            "standby_speed": {
                "pid": 707,
                "desc": "Set standby rotation speed (%)",
                "type": "u_integer",
                "write": True
            },
            "vent_mode": {
                "pid": 30,
                "desc": "Set venting valve mode",
                "type": "u_integer",
                "write": True,
                "options": ["0", "1", "2"],
                "option_desc": ["Closed", "Controlled", "Open"]
            },
            "vent_time": {
                "pid": 721,
                "desc": "Set venting time (seconds)",
                "type": "u_integer",
                "write": True,
                "unit": "sec",
                "min": 1,
                "max": 3600
            },
            "firmware_version": {
                "pid": 312,
                "desc": "Read firmware version",
                "type": "string"
            },
            "pump_type": {
                "pid": 369,
                "desc": "Read pump type",
                "type": "string"
            },
            "station_number": {
                "pid": 797,
                "desc": "Set station address",
                "type": "u_integer",
                "write": True,
                "min": 1,
                "max": 255
            },
            "baud_rate": {
                "pid": 798,
                "desc": "Set communication baud rate",
                "type": "u_integer",
                "write": True,
                "options": ["9600", "19200", "38400"],
                "option_desc": ["9600 baud", "19200 baud", "38400 baud"]
            },
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
        Constructs a command frame for the TC600 controller.
        For write commands, parameters are encoded as fixed-width ASCII strings.
        The final command is terminated by a carriage return after appending a 3-digit checksum.

        Args:
            command (TurboCommand): The turbo command to serialize.

        Returns:
            bytes: The ASCII-encoded command frame.
        """
        if command.name not in self._command_defs:
            raise ValueError(f"Unknown command: {command.name}")
        cmd_info = self._command_defs[command.name]
        self.current_command = command.name

        # Format the address (always 3 digits in RS485 mode; else default "254")
        addr = f"{self.address:03d}"
        action = "10" if command.command_type == "!" else "00"
        param = f"{cmd_info['pid']:03d}"

        if command.command_type == "!":
            value = command.parameters.get("value", 0)
            data_bytes = self._encode_value(value, cmd_info.get("type"))
            data_len = f"{len(data_bytes):02d}"
            msg = f"{addr}{action}{param}{data_len}{data_bytes}"
        else:
            msg = f"{addr}{action}{param}02=?"

        # Calculate checksum as the sum of the ASCII values modulo 256.
        checksum = sum(msg.encode("ascii")) % 256
        msg = f"{msg}{checksum:03d}\r"
        return msg.encode("ascii")

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """
        Parses the ASCII response from the TC600 controller.

        Args:
            response (bytes): The raw response.

        Returns:
            dict: Parsed response data.
        """
        try:
            resp_str = response.decode("ascii").strip()
            if len(resp_str) < 10:
                return self._error_response("Response too short", response)
            addr = resp_str[0:3]
            action = resp_str[3:5]
            param = resp_str[5:8]
            data = resp_str[10:-4] if len(resp_str) > 12 else ""
            if "NO_DEF" in resp_str:
                return self._error_response("Parameter does not exist", response)
            if "_RANGE" in resp_str:
                return self._error_response("Value out of range", response)
            if "_LOGIC" in resp_str:
                return self._error_response("Command logic error", response)
            return {
                "success": True,
                "raw_data": response,
                "formatted_data": self._format_response_data(data)
            }
        except Exception as e:
            return self._error_response(f"Parse error: {str(e)}", response)

    def _encode_value(self, value: Any, data_type: str) -> str:
        """
        Encodes a value for a write command into a fixed-width string based on its type.

        Args:
            value: The value to encode.
            data_type (str): The type of the value (e.g., "boolean_old", "u_integer", "u_real", "string").

        Returns:
            str: The encoded value as a string.

        Raises:
            ValueError: If the data type is unsupported.
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
        Formats the response data based on the current command.

        Args:
            data (str): The raw data string from the response.

        Returns:
            str: A formatted string including units if applicable.
        """
        if not data or data.isspace():
            return "No data"
        cmd_info = self._command_defs.get(self.current_command, {})
        if len(data) == 6 and all(c in "01" for c in data):
            return "On" if data == "111111" else "Off"
        if cmd_info.get("type") in ["u_integer", "u_real"]:
            try:
                value = int(data)
                if self.current_command == "get_speed":
                    return f"{value} RPM"
                elif "unit" in cmd_info:
                    return f"{value} {cmd_info['unit']}"
                return str(value)
            except ValueError:
                pass
        return data

    def _error_response(self, message: str, response: bytes) -> Dict[str, Any]:
        self.logger.error(message)
        return {
            "success": False,
            "error": message,
            "raw_data": response,
            "formatted_data": f"Error: {message}"
        }
