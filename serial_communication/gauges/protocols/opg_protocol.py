"""
Implements protocol logic for OPG550 optical plasma gauge.
"""

import struct
from typing import Dict, Any

from serial_communication.gauges.commands.opg_commands import OPGCommand
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand
from serial_communication.param_types import ParamType


class OPGProtocol(GaugeProtocol):
    """
    Handles commands for OPG550 optical plasma gauge using a protocol version 2 frame.
    """

    def __init__(self, address: int = 254, logger: Any = None):
        super().__init__(address, logger)
        self.device_id = 0x0B  # OPG device ID

    def _initialize_commands(self):
        for cmd in vars(OPGCommand).values():
            if hasattr(cmd, "pid"):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: GaugeCommand) -> bytes:
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")

        msg = bytearray([
            0x00,        # Address (RS232 only for OPG)
            self.device_id,
            0x20,        # Protocol version 2
            0x00, 0x05,  # Message length
            0x01 if cmd_def.read else 0x03,
            (cmd_def.pid >> 8) & 0xFF,
            cmd_def.pid & 0xFF,
            0x00, 0x00   # Index bytes
        ])

        if command.command_type == "!" and command.parameters and cmd_def.write:
            param_bytes = self._encode_param(command.parameters.get("value", 0), cmd_def.param_type)
            msg.extend(param_bytes)

            length_bytes = (len(msg) - 5).to_bytes(2, byteorder='big')
            msg[3], msg[4] = length_bytes[0], length_bytes[1]

        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        if len(response) < 11:
            return self._error_response("Response too short")

        device_id = response[1]
        protocol_ver = (response[2] >> 4) & 0x0F
        msg_length = (response[3] << 8) | response[4]
        pid = (response[6] << 8) | response[7]

        if device_id != self.device_id:
            return self._error_response("Invalid device ID")
        if protocol_ver != 2:
            return self._error_response("Invalid protocol version")
        if len(response) != msg_length + 11:
            return self._error_response("Invalid message length")

        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        data = response[10:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        if pid == OPGCommand.PRESSURE.pid:
            pressure = struct.unpack(">f", data)[0]
            return {"success": True, "pressure": pressure, "unit": "mbar"}
        elif pid == OPGCommand.PLASMA_STATUS.pid:
            status = data[0]
            return {
                "success": True,
                "plasma_status": {
                    "off": status == 0,
                    "striking": status == 1,
                    "on": status == 2
                }
            }
        elif pid == OPGCommand.SELF_TEST.pid:
            val = data[0]
            return {
                "success": True,
                "diagnostic": {
                    "ok": val == 0,
                    "service_needed": val == 1,
                    "failure": val == 2
                }
            }
        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        if param_type == ParamType.FLOAT:
            return struct.pack(">f", float(value))
        return bytes([0])

    def _error_response(self, message: str) -> Dict[str, Any]:
        self.logger.error(message)
        return {"success": False, "error": message}
