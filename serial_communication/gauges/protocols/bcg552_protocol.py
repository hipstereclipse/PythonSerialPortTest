"""
Implements the protocol logic for BCG552 TripleGauge.
"""

import struct
from typing import Dict, Any

from serial_communication.gauges.commands.bcg552_commands import BCG552Command
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand
from serial_communication.param_types import ParamType


class BCG552Protocol(GaugeProtocol):
    """
    Handles commands for BCG552 triple gauge devices.
    """

    def _initialize_commands(self):
        for cmd in vars(BCG552Command).values():
            if hasattr(cmd, 'pid'):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: GaugeCommand) -> bytes:
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")

        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,
            0x02,  # Device ID for BCG552
            0x00,
            0x05,
            0x01 if cmd_def.read else 0x03,
            (cmd_def.pid >> 8) & 0xFF,
            cmd_def.pid & 0xFF,
            0x00, 0x00
        ])

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

        if device_id != 0x02:
            return self._error_response("Invalid device ID")

        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        if pid == BCG552Command.PRESSURE.pid:
            # LogFixs32en26 format
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {"success": True, "pressure": pressure, "unit": "mbar"}

        elif pid == BCG552Command.TEMPERATURE.pid:
            temp = struct.unpack('>f', data)[0]
            return {"success": True, "temperature": temp, "unit": "C"}

        elif pid == BCG552Command.ERROR_STATUS.pid:
            error_flags = int.from_bytes(data, byteorder='big')
            return {
                "success": True,
                "errors": {
                    "sensor_error": bool(error_flags & 0x01),
                    "electronics_error": bool(error_flags & 0x02),
                    "calibration_error": bool(error_flags & 0x04),
                    "memory_error": bool(error_flags & 0x08),
                }
            }

        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        if param_type == ParamType.UINT8:
            return bytes([int(value) & 0xFF])
        elif param_type == ParamType.UINT16:
            return int(value).to_bytes(2, byteorder='big')
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes([0])

    def _error_response(self, message: str) -> Dict[str, Any]:
        self.logger.error(message)
        return {"success": False, "error": message}
