#!/usr/bin/env python3
"""
ppg_protocol.py

Implements the protocol for PPG550/PPG570 MEMS Pirani & Piezo gauges.
These devices use an ASCII-based protocol. Commands are built as ASCII strings and
responses are parsed from ASCII text.

Usage Example:
    protocol = PPGProtocol(address=254, gauge_type="PPG550")
    cmd = GaugeCommand(name="pressure", command_type="?")
    command_bytes = protocol.create_command(cmd)
    response = protocol.parse_response(received_bytes)
"""

from typing import Optional, List, Dict, Any

from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand, GaugeResponse

class PPGProtocol(GaugeProtocol):
    """
    Protocol implementation for PPG550/PPG570 gauges.
    """

    def __init__(self, address: int = 254, gauge_type: str = "PPG550", logger: Optional[Any] = None):
        """
        Initializes the PPGProtocol.

        Args:
            address (int): The device address.
            gauge_type (str): Either "PPG550" or "PPG570".
            logger (Optional[Any]): Logger instance.
        """
        self.gauge_type = gauge_type
        # PPG570 devices have an additional atmospheric sensor.
        self.has_atm = (gauge_type == "PPG570")
        super().__init__(address, logger)
        self.logger.debug(f"Initialized {self.gauge_type} protocol handler with ATM sensor: {self.has_atm}")

    def _initialize_commands(self) -> None:
        """
        Defines the set of ASCII commands for PPG gauges.
        """
        self._command_defs = {
            "pressure": {"cmd": "PR3", "type": "read", "desc": "Read pressure measurement"},
            "temperature": {"cmd": "T", "type": "read", "desc": "Read temperature"},
            "software_version": {"cmd": "FV", "type": "read", "desc": "Read firmware version"},
            "serial_number": {"cmd": "SN", "type": "read", "desc": "Read serial number"},
            "unit": {"cmd": "U", "type": "read/write", "desc": "Get/set pressure unit"},
            "zero_adjust": {"cmd": "VAC", "type": "write", "desc": "Perform zero adjustment"},
            "piezo_adjust": {"cmd": "FS", "type": "write", "desc": "Perform full scale adjustment"}
        }
        if self.has_atm:
            self._command_defs.update({
                "atm_pressure": {"cmd": "PR4", "type": "read", "desc": "Read atmospheric pressure"},
                "differential_pressure": {"cmd": "PR5", "type": "read", "desc": "Read differential pressure"},
                "atm_zero": {"cmd": "ATZ", "type": "write", "desc": "Perform atmospheric sensor zero adjustment"},
                "atm_adjust": {"cmd": "ATD", "type": "write", "desc": "Perform atmospheric sensor adjustment"}
            })

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Creates an ASCII command string for the PPG gauge.
        Format: "@<address><cmd><? or !>[parameter]\\"

        Args:
            command (GaugeCommand): The command to serialize.

        Returns:
            bytes: The ASCII-encoded command.
        """
        cmd_info = self._command_defs.get(command.name)
        if not cmd_info:
            raise ValueError(f"Unknown command: {command.name}")
        # If using RS485, format the address as a three-digit number; otherwise, default to "254"
        addr = f"{self.address:03d}" if self.rs485_mode else "254"
        cmd_type = "!" if command.command_type in ["!", "write"] else "?"
        cmd_str = f"@{addr}{cmd_info['cmd']}{cmd_type}"
        if cmd_type == "!" and command.parameters:
            value = command.parameters.get("value")
            if value is not None:
                cmd_str += str(value)
        cmd_str += "\\"
        self.logger.debug(f"Created PPG command: {cmd_str}")
        return cmd_str.encode("ascii")

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Parses an ASCII response from the PPG gauge.
        Expected responses start with '@' and end with ';FF'.

        Args:
            response (bytes): The raw response bytes.

        Returns:
            GaugeResponse: The parsed response.
        """
        try:
            resp_str = response.decode("ascii", errors="replace").strip()
            self.logger.debug(f"Parsing PPG response: {resp_str}")
            if resp_str.startswith("@NAK"):
                error_msg = resp_str[4:].strip() or "Command failed"
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=error_msg,
                    success=False,
                    error_message=error_msg
                )
            if resp_str.startswith("@ACK"):
                data = resp_str[4:-3].strip()
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=data,
                    success=True
                )
            return GaugeResponse(
                raw_data=response,
                formatted_data=resp_str,
                success=False,
                error_message="Invalid response format"
            )
        except Exception as e:
            self.logger.error(f"PPG response parse error: {str(e)}")
            return GaugeResponse(
                raw_data=response if response else b"",
                formatted_data="",
                success=False,
                error_message=f"Parse error: {str(e)}"
            )

    def test_commands(self) -> List[bytes]:
        """
        Generates a list of test commands for PPG gauges.

        Returns:
            List[bytes]: A list of ASCII command frames.
        """
        commands = [
            self.create_command(GaugeCommand(name="software_version", command_type="?")),
            self.create_command(GaugeCommand(name="pressure", command_type="?"))
        ]
        if self.has_atm:
            commands.append(self.create_command(GaugeCommand(name="atm_pressure", command_type="?")))
        return commands
