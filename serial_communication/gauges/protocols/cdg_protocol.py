"""
Implements the protocol logic for CDG gauges, including creation and parsing of command frames.
"""

from typing import Any, List

from serial_communication.gauges.commands.cdg_commands import CDGCommand
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.param_types import ParamType


class CDGProtocol(GaugeProtocol):
    """
    Implements the custom frame structure and logic for CDG gauges.
    """

    def _initialize_commands(self):
        for cmd in vars(CDGCommand).values():
            if isinstance(cmd, dict) or hasattr(cmd, 'pid'):
                # Each command is a CommandDefinition
                self._command_defs[cmd.name] = cmd

    def test_commands(self) -> List[bytes]:
        """
        Returns some basic test commands used to verify connectivity with a gauge.
        """
        commands = []

        # Adds user interface button for reading page 0
        test_cmd1 = bytearray([0x03, 0x00, 0x00, 0x00, 0x00])
        test_cmd1[4] = sum(test_cmd1[1:4]) & 0xFF
        commands.append(bytes(test_cmd1))

        # Adds user interface button for reading temperature status
        test_cmd2 = bytearray([0x03, 0x00, 0x02, 0x00, 0x00])
        test_cmd2[4] = sum(test_cmd2[1:4]) & 0xFF
        commands.append(bytes(test_cmd2))

        # Adds user interface button for reading unit
        test_cmd3 = bytearray([0x03, 0x00, 0x01, 0x00, 0x00])
        test_cmd3[4] = sum(test_cmd3[1:4]) & 0xFF
        commands.append(bytes(test_cmd3))

        return commands

    def is_valid_response(self, response: bytes) -> bool:
        """
        Returns True if the response bytes match the expected format.
        """
        if len(response) != 9:
            return False
        if response[0] != 0x07:
            return False
        calc_checksum = sum(response[1:8]) & 0xFF
        if calc_checksum != response[8]:
            return False
        return True

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Builds and returns the 5-byte command frame for CDG gauges.
        """
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")

        msg = bytearray([0x03, 0x00, cmd_def.pid, 0x00, 0x00])

        if command.command_type == "!" and command.parameters:
            msg[1] = 0x10
            msg[3] = self._encode_param(command.parameters.get('value', 0), cmd_def.param_type)
        else:
            msg[1] = 0x00

        msg[4] = sum(msg[1:4]) & 0xFF
        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Reads CDG response bytes and returns a structured GaugeResponse.
        """
        if not self.is_valid_response(response):
            return GaugeResponse(
                raw_data=response,
                formatted_data="Invalid response format",
                success=False,
                error_message="Response validation failed"
            )

        try:
            status = response[2]
            error_byte = response[3]
            pressure_high = response[4]
            pressure_low = response[5]

            pressure_value = (pressure_high << 8) | pressure_low
            if pressure_value & 0x8000:
                pressure_value = -((~pressure_value + 1) & 0xFFFF)
            pressure = pressure_value / 16384.0

            formatted_data = {
                "pressure": pressure,
                "unit": self._get_unit_string(status),
                "status": {
                    "heating": bool(status & 0x80),
                    "temp_ok": bool(status & 0x40),
                    "emission": bool(status & 0x20)
                },
                "errors": self._parse_error_byte(error_byte)
            }

            return GaugeResponse(
                raw_data=response,
                formatted_data=str(formatted_data),
                success=True
            )
        except Exception as e:
            return GaugeResponse(
                raw_data=response,
                success=False,
                error_message=f"Parse error: {str(e)}"
            )

    def _get_unit_string(self, status_byte: int) -> str:
        unit_bits = (status_byte >> 4) & 0x03
        units = {
            0: "mbar",
            1: "Torr",
            2: "Pa"
        }
        return units.get(unit_bits, "unknown")

    def _parse_error_byte(self, error: int):
        return {
            "sync_error": bool(error & 0x01),
            "invalid_command": bool(error & 0x02),
            "invalid_access": bool(error & 0x04),
            "hardware_error": bool(error & 0x08)
        }

    def _encode_param(self, value: Any, param_type: ParamType) -> int:
        if param_type == ParamType.UINT8:
            return int(value) & 0xFF
        elif param_type == ParamType.UINT16:
            return int(value) & 0xFFFF
        elif param_type == ParamType.FLOAT:
            return int(value * 16384.0) & 0xFFFF
        return 0
