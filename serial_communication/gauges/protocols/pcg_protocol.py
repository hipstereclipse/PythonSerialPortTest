"""
Implements protocol logic for PCG550/PSG550 gauges.
"""

import struct
from typing import Dict, Any, Optional

from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand
from serial_communication.param_types import CommandDefinition, ParamType


class PCGProtocol(GaugeProtocol):
    """
    Handles PCG/PSG gauge commands using a binary protocol structure.
    """

    def __init__(self, address: int = 254, logger: Optional[object] = None):
        super().__init__(address, logger)
        self.device_id = 0x02  # PCG/PSG device ID

    def _initialize_commands(self):
        """
        Adds user interface button for commands specific to PCG/PSG.
        """
        self._command_defs = {
            "pressure": CommandDefinition(221, "pressure", "Read pressure measurement", True, False),
            "temperature": CommandDefinition(222, "temperature", "Read temperature", True, False),
            "zero_adjust": CommandDefinition(417, "zero_adjust", "Execute zero adjustment", False, True),
            "software_version": CommandDefinition(218, "software_version", "Read software version", True, False),
            "serial_number": CommandDefinition(207, "serial_number", "Read serial number", True, False),
            "error_status": CommandDefinition(228, "error_status", "Read error status", True, False)
        }

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Builds command frame for PCG/PSG devices.
        """
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

        # Adds user interface button for writing parameters
        if command.command_type == "!" and command.parameters and cmd_def.write:
            param_bytes = self._encode_param(command.parameters.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4

        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """
        Interprets the PCG/PSG response based on message length, CRC, and PID.
        """
        if len(response) < 7:
            return self._error_response("Response too short")

        device_id = response[1]
        msg_length = response[3]
        pid = (response[5] << 8) | response[6]

        # Verifies device ID
        if device_id != self.device_id:
            return self._error_response("Invalid device ID")

        # Verifies message length
        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Checks CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """
        Parses the data portion of the PCG response.
        """
        if pid == 221:  # Pressure
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 20))
            return {"success": True, "pressure": pressure, "unit": "mbar"}
        elif pid == 222:  # Temperature
            temp = struct.unpack('>f', data)[0]
            return {"success": True, "temperature": temp, "unit": "C"}
        elif pid == 228:  # Error status
            error_flags = int.from_bytes(data, byteorder='big')
            return {"success": True, "errors": self._parse_error_flags(error_flags)}

        # Returns raw data for unknown PIDs
        return {"success": True, "raw_data": data.hex()}

    def _parse_error_flags(self, flags: int) -> Dict[str, bool]:
        return {
            "sensor_error": bool(flags & 0x01),
            "electronics_error": bool(flags & 0x02),
            "calibration_error": bool(flags & 0x04),
            "memory_error": bool(flags & 0x08)
        }

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        """
        Encodes a parameter into the correct byte structure.
        """
        if param_type == ParamType.UINT8:
            return bytes([int(value) & 0xFF])
        elif param_type == ParamType.UINT16:
            return int(value).to_bytes(2, byteorder='big')
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes()

    def _error_response(self, message: str) -> Dict[str, Any]:
        self.logger.error(message)
        return {"success": False, "error": message}
