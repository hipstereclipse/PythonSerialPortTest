"""
Implements the protocol logic for BCG450 combination gauges.
"""

import struct
from typing import Dict, Any
from serial_communication.models import GaugeCommand, GaugeResponse
from .gauge_protocol import GaugeProtocol
from ..commands.bcg450_commands import BCG450Command
from ...param_types import ParamType


class BCG450Protocol(GaugeProtocol):
    """
    Manages creation and parsing of BCG450 gauge commands and responses.
    """

    def _initialize_commands(self):
        # Adds user interface button for each BCG450Command definition
        for cmd in vars(BCG450Command).values():
            if hasattr(cmd, "pid"):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: GaugeCommand) -> bytes:
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")

        # Builds command frame
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,
            0x0B,                # BCG device ID
            0x00,                # ACK bit and message length
            0x05,                # Default message length
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,
            cmd_def.pid & 0xFF,
            0x00, 0x00
        ])

        # Adds user interface button for writing parameters
        if command.command_type == "!" and command.parameters and cmd_def.write:
            param_bytes = self._encode_param(command.parameters.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4

        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        if len(response) < 7:
            return self._error_response("Response too short")

        device_id = response[1]
        msg_length = response[3]
        pid = (response[5] << 8) | response[6]

        if device_id != 0x0B:
            return self._error_response("Invalid device ID")

        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        if pid == BCG450Command.PRESSURE.pid:
            value = int.from_bytes(data, byteorder='big', signed=True)
            # BCG uses LogFixs32en26 format
            pressure = 10 ** (value / (2 ** 26))
            return {"success": True, "pressure": pressure, "unit": "mbar"}

        elif pid == BCG450Command.SENSOR_STATUS.pid:
            status = data[0]
            return {
                "success": True,
                "sensor_status": {
                    "pirani_active": bool(status & 0x01),
                    "ba_active": bool(status & 0x02),
                    "cdg_active": bool(status & 0x04),
                    "degas_active": bool(status & 0x08),
                }
            }
        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        if param_type == ParamType.BOOL:
            return bytes([1 if value else 0])
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes([0])

    def _error_response(self, message: str) -> Dict[str, Any]:
        self.logger.error(message)
        return {"success": False, "error": message}
