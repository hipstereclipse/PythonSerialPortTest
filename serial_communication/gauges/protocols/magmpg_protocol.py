"""
Implements protocol logic for MAG500 and MPG500 combination gauges.
"""

import struct
from typing import Dict, Any, Optional

from serial_communication.gauges.commands.magmpg_commands import MAG500Command, MPG500Command
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand
from serial_communication.param_types import ParamType


class MAGMPGProtocol(GaugeProtocol):
    """
    Combines logic for both MAG500 (device_id=0x14) and MPG500 (device_id=0x04).
    """

    def __init__(self, device_id: int = 0x14, address: int = 254, logger: Optional[object] = None):
        super().__init__(address, logger)
        self.device_id = device_id

    def _initialize_commands(self):
        # Chooses command set based on device_id
        command_class = MAG500Command if self.device_id == 0x14 else MPG500Command
        for cmd in vars(command_class).values():
            if hasattr(cmd, "pid"):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: GaugeCommand) -> bytes:
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")

        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,
            self.device_id,
            0x00,
            0x05,
            0x01 if cmd_def.read else 0x03,
            (cmd_def.pid >> 8) & 0xFF,
            cmd_def.pid & 0xFF,
            0x00, 0x00
        ])

        if command.command_type == "!" and command.parameters and cmd_def.write:
            param_bytes = self._encode_param(command.parameters.get("value", 0), cmd_def.param_type)
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

        if device_id != self.device_id:
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
        if pid == 221:  # pressure
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {"success": True, "pressure": pressure, "unit": "mbar"}
        elif pid == 222:  # temperature
            temp = struct.unpack('>f', data)[0]
            return {"success": True, "temperature": temp, "unit": "C"}
        elif pid == 223:  # active_sensor
            status = data[0]
            return {
                "success": True,
                "active_sensor": {
                    "ccig": bool(status & 0x01),
                    "pirani": bool(status & 0x02),
                    "mixed": bool(status & 0x04)
                }
            }
        elif pid == 533:  # ccig_status for MAG500
            status = data[0]
            return {
                "success": True,
                "ccig_status": {
                    "off": status == 0,
                    "on_not_ignited": status == 1,
                    "on_ignited": status == 3
                }
            }
        elif pid == 228:  # error_status
            error_flags = int.from_bytes(data, byteorder='big')
            return {
                "success": True,
                "errors": {
                    "no_error": error_flags == 0,
                    "eeprom_timeout": bool(error_flags & 0x01),
                    "eeprom_crc": bool(error_flags & 0x02),
                    "eeprom_error": bool(error_flags & 0x04),
                    "pirani_filament": bool(error_flags & 0x08),
                    "ccig_short": bool(error_flags & 0x800),
                }
            }
        elif pid == 104:  # run_hours
            hours = int.from_bytes(data, byteorder='big') * 0.25
            return {"success": True, "run_hours": hours}

        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        if param_type == ParamType.BOOL:
            return bytes([1 if value else 0])
        elif param_type == ParamType.UINT32:
            return int(value).to_bytes(4, byteorder='big')
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes([0])

    def _error_response(self, message: str) -> Dict[str, Any]:
        self.logger.error(message)
        return {"success": False, "error": message}
