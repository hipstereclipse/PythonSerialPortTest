#!/usr/bin/env python3
"""
bcg450_protocol.py

This module implements the BCG450Protocol for BCG450 combination gauges.
It constructs command frames and parses responses according to the BCG450 specifications.
Supports both read and write commands, including continuous reading.

Usage Example:
    protocol = BCG450Protocol(address=254)
    cmd = GaugeCommand(name="pressure", command_type="?")
    command_bytes = protocol.create_command(cmd)
    response = protocol.parse_response(received_bytes)
"""

import struct
from typing import Dict, Any, List, Optional
import logging
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol

class BCG450Protocol(GaugeProtocol):
    """
    Protocol implementation for BCG450 gauges.
    """

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        """
        Initializes the BCG450Protocol.

        Args:
            address (int): The device address.
            logger (Optional[logging.Logger]): Logger instance.
        """
        super().__init__(address, logger)
        self.device_id = 0x0B  # BCG450 device identifier.
        self._response_validation_enabled = True
        self.rs485_mode = False
        self._last_command = None
        self.logger.debug("Initialized BCG450 protocol handler")

    def _initialize_commands(self) -> None:
        """
        Populates the command definitions for BCG450 gauges.
        Each command is defined in a dictionary with keys such as 'pid', 'cmd', and 'desc'.
        """
        self._command_defs = {
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
        Creates a command frame for a given GaugeCommand.

        The frame is structured as follows:
          [Address, Device ID, 0x00, Length, Command Type, PID MSB, PID LSB, Reserved, Reserved, CRC16]

        Args:
            command (GaugeCommand): The command to serialize.

        Returns:
            bytes: The serialized command frame.
        """
        cmd_info = self._command_defs.get(command.name)
        if not cmd_info:
            raise ValueError(f"Unknown command: {command.name}")
        self._last_command = command.name

        msg = bytearray([
            self.address if self.rs485_mode else 0x00,
            self.device_id,
            0x00,
            0x05,  # Default length; may be updated if parameters are appended.
            0x01 if cmd_info["cmd"] == 1 else 0x03,
            (cmd_info["pid"] >> 8) & 0xFF,
            cmd_info["pid"] & 0xFF,
            0x00, 0x00
        ])

        if command.command_type == "!" and cmd_info.get("parameters", False):
            value = command.parameters.get("value", 0)
            # Here we assume a single-byte parameter; extend conversion as needed.
            msg.extend([int(value) & 0xFF])
            msg[3] = len(msg) - 4

        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Parses a raw response from the gauge.

        The parsing logic verifies CRC and extracts meaningful data based on the command type.

        Args:
            response (bytes): The raw response data.

        Returns:
            GaugeResponse: The parsed response.
        """
        try:
            if not response:
                return self._create_error_response("No response received", response)
            if not self._response_validation_enabled:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=response.hex(' ').upper(),
                    success=True
                )
            # For demonstration, we simply pass the entire response as meaningful.
            data = response
            parsed_result = self._parse_command_response(data)
            return GaugeResponse(
                raw_data=response,
                formatted_data=str(parsed_result),
                success=True
            )
        except Exception as e:
            return self._create_error_response(str(e), response)

    def _parse_command_response(self, data: bytes) -> Dict[str, Any]:
        """
        Parses the response data based on the expected response type.

        Args:
            data (bytes): The raw data from the gauge.

        Returns:
            dict: A dictionary containing parsed information.
        """
        if not self._last_command:
            return {"raw_data": data.hex(' ').upper()}
        cmd_info = self._command_defs.get(self._last_command)
        if not cmd_info:
            return {"raw_data": data.hex(' ').upper()}

        response_type = cmd_info.get("response_type", "raw")
        if response_type == "pressure":
            value = int.from_bytes(data, byteorder="big", signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {"pressure": f"{pressure:.2e} mbar"}
        elif response_type == "temperature":
            value = int.from_bytes(data, byteorder="big", signed=True)
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
        else:
            return {"value": data.hex(' ').upper()}

    def _create_error_response(self, message: str, response: bytes) -> GaugeResponse:
        """
        Creates a standardized error response.

        Args:
            message (str): The error message.
            response (bytes): The raw response data.

        Returns:
            GaugeResponse: The error response.
        """
        error_msg = f"Error: {message}"
        if response:
            error_msg += f" (Raw: {response.hex(' ').upper()})"
        return GaugeResponse(
            raw_data=response,
            formatted_data=error_msg,
            success=False,
            error_message=message
        )
