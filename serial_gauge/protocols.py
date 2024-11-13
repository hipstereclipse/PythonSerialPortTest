# Import required modules
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple, Union
import struct
import math
import binascii
import logging
from dataclasses import dataclass
from enum import Enum

from serial_gauge.models import GaugeCommand, GaugeResponse


# Define command parameter types
class ParamType(Enum):
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"


@dataclass
class CommandDefinition:
    """Defines a gauge command with its properties"""
    pid: int  # Protocol ID / Command ID
    name: str  # Command name
    description: str  # Command description
    read: bool = False  # Supports read
    write: bool = False  # Supports write
    continuous: bool = False  # Available in continuous output
    param_type: Optional[ParamType] = None  # Parameter type if needed
    min_value: Optional[Union[int, float]] = None  # Minimum value if applicable
    max_value: Optional[Union[int, float]] = None  # Maximum value if applicable
    units: Optional[str] = None  # Units for the value


class CDGCommand:
    """Command definitions for CDG gauges"""
    PRESSURE = CommandDefinition(0xDD, "pressure", "Read pressure measurement", True, False, True)
    TEMPERATURE = CommandDefinition(0xDE, "temperature", "Read sensor temperature", True, False)
    ZERO_ADJUST = CommandDefinition(0x02, "zero_adjust", "Perform zero adjustment", False, True)
    FULL_SCALE = CommandDefinition(0x03, "full_scale", "Set full scale value", True, True, False, ParamType.FLOAT)
    SOFTWARE_VERSION = CommandDefinition(0x10, "software_version", "Read software version", True, False)
    UNIT = CommandDefinition(0x01, "unit", "Get/set pressure unit", True, True, False, ParamType.UINT8)
    FILTER = CommandDefinition(0x02, "filter", "Get/set filter mode", True, True, False, ParamType.UINT8)

class PPG550Command:
    """Command definitions for PPG550 MEMS Pirani & Piezo gauge"""
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure measurement", True, False, True)
    TEMPERATURE = CommandDefinition(222, "temperature", "Read sensor temperature", True, False)
    SERIAL_NUMBER = CommandDefinition(207, "serial_number", "Read serial number", True, False)
    SOFTWARE_VERSION = CommandDefinition(218, "software_version", "Read software version", True, False)
    ZERO_ADJUST = CommandDefinition(417, "zero_adjust", "Execute zero adjustment", False, True)
    PIEZO_FULL_SCALE = CommandDefinition(33000, "piezo_full_scale", "Read Piezo full scale", True, False)
    PIRANI_ADJUST = CommandDefinition(418, "pirani_adjust", "Execute Pirani adjustment", False, True)
    UNIT = CommandDefinition(224, "unit", "Get/set pressure unit", True, True, False, ParamType.UINT8)

class PPG570Command(PPG550Command):
    """Command definitions for PPG570 with additional ATM sensor"""
    ATM_ZERO = CommandDefinition(419, "atm_zero", "Execute ATM sensor zero adjustment", False, True)
    ATM_FULL_SCALE = CommandDefinition(420, "atm_full_scale", "ATM sensor full scale adjustment", False, True)
    ATM_PRESSURE = CommandDefinition(223, "atm_pressure", "Read atmospheric pressure", True, False)
    DIFF_PRESSURE = CommandDefinition(225, "diff_pressure", "Read differential pressure", True, False)

class BPG40xCommand:
    """Command definitions for BPG hot cathode gauges"""
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure measurement", True, False, True)
    EMISSION_STATUS = CommandDefinition(533, "emission_status", "Get emission status", True, False)
    DEGAS = CommandDefinition(529, "degas", "Control degas function", False, True, False, ParamType.BOOL)
    EMISSION_CURRENT = CommandDefinition(530, "emission_current", "Get/set emission current", True, True)
    FILAMENT_SELECT = CommandDefinition(531, "filament_select", "Select active filament", False, True)

class BPG552Command:
    """Command definitions for BPG552 hot cathode gauges"""
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure measurement", True, False, True)
    TEMPERATURE = CommandDefinition(222, "temperature", "Read sensor temperature", True, False)
    ZERO_ADJUST = CommandDefinition(417, "zero_adjust", "Execute zero adjustment", False, True)
    SOFTWARE_VERSION = CommandDefinition(218, "software_version", "Read software version", True, False)
    SERIAL_NUMBER = CommandDefinition(207, "serial_number", "Read serial number", True, False)
    ERROR_STATUS = CommandDefinition(228, "error_status", "Read error status", True, False)
    EMISSION_STATUS = CommandDefinition(533, "emission_status", "Get emission status", True, False)
    DEGAS = CommandDefinition(529, "degas", "Control degas function", False, True, False, ParamType.BOOL)
    EMISSION_CURRENT = CommandDefinition(530, "emission_current", "Get/set emission current", True, True)


class BCG450Command:
    """Command definitions for BCG combination gauges"""
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure measurement", True, False, True)
    SENSOR_STATUS = CommandDefinition(223, "sensor_status", "Get active sensor status", True, False)
    PIRANI_ADJ = CommandDefinition(418, "pirani_adjust", "Adjust Pirani sensor", False, True)
    BA_DEGAS = CommandDefinition(529, "ba_degas", "Control BA degas", False, True)

class BCG552Command:
    """Command definitions for BCG552 gauges"""
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure measurement", True, False, True)
    TEMPERATURE = CommandDefinition(222, "temperature", "Read sensor temperature", True, False)
    ZERO_ADJUST = CommandDefinition(417, "zero_adjust", "Perform zero adjustment", False, True)
    SOFTWARE_VERSION = CommandDefinition(218, "software_version", "Read software version", True, False)
    SERIAL_NUMBER = CommandDefinition(207, "serial_number", "Read serial number", True, False)
    ERROR_STATUS = CommandDefinition(228, "error_status", "Read error status", True, False)

class MAG500Command:
    """Command definitions for MAG500 cold cathode gauges"""
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure (LogFixs32en26)", True, False, True)
    TEMPERATURE = CommandDefinition(222, "temperature", "Read temperature", True, False)
    SERIAL_NUMBER = CommandDefinition(207, "serial_number", "Read serial number", True, False)
    SOFTWARE_VERSION = CommandDefinition(218, "software_version", "Read software version", True, False)
    ERROR_STATUS = CommandDefinition(228, "device_exception", "Read device errors", True, False)
    RUN_HOURS = CommandDefinition(104, "run_hours", "Read operating hours", True, False)
    CCIG_STATUS = CommandDefinition(533, "ccig_status", "CCIG Status (0=off, 1=on not ignited, 3=on and ignited)", True, False)
    CCIG_CONTROL = CommandDefinition(529, "ccig_control", "Switch CCIG on/off", False, True)
    CCIG_FULL_SCALE = CommandDefinition(503, "ccig_full_scale", "Read CCIG full scale", True, False)
    CCIG_SAFE_STATE = CommandDefinition(504, "ccig_safe_state", "Read CCIG safe state", True, False)

class MPG500Command:
    """Command definitions for MPG500 combination gauges"""
    PRESSURE = CommandDefinition(221, "pressure", "Read pressure (LogFixs32en26)", True, False, True)
    TEMPERATURE = CommandDefinition(222, "temperature", "Read temperature", True, False)
    SERIAL_NUMBER = CommandDefinition(207, "serial_number", "Read serial number", True, False)
    SOFTWARE_VERSION = CommandDefinition(218, "software_version", "Read software version", True, False)
    ERROR_STATUS = CommandDefinition(228, "device_exception", "Read device errors", True, False)
    RUN_HOURS = CommandDefinition(104, "run_hours", "Read operating hours", True, False)
    ACTIVE_SENSOR = CommandDefinition(223, "active_sensor", "Current active sensor (1=CCIG, 2=Pirani, 3=Mixed)", True, False)
    PIRANI_FULL_SCALE = CommandDefinition(33000, "pirani_full_scale", "Read Pirani full scale", True, False)
    PIRANI_ADJUST = CommandDefinition(418, "pirani_adjust", "Execute Pirani adjustment", False, True)


class GaugeProtocol(ABC):
    """Base protocol class for all gauge communications"""

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        """Initialize protocol with optional address for RS485"""
        self.address = address
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.rs485_mode = False
        self._command_defs = {}  # Command definitions dictionary
        self._initialize_commands()

    @abstractmethod
    def _initialize_commands(self):
        """Initialize command definitions for the gauge"""
        pass

    @abstractmethod
    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create command bytes for transmission"""
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse response bytes into structured data"""
        pass

    def set_rs485_mode(self, enabled: bool):
        """Enable or disable RS485 mode"""
        self.rs485_mode = enabled

    def calculate_crc16(self, data: bytes) -> int:
        """Calculate CRC16 with CCITT polynomial"""
        crc = 0xFFFF
        for byte in data:
            crc = crc ^ (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                crc = crc & 0xFFFF
        return crc


class CDGProtocol(GaugeProtocol):
    """Protocol implementation for CDG025D and CDG045D gauges"""

    def _initialize_commands(self):
        """Initialize CDG gauge commands"""
        for cmd in vars(CDGCommand).values():
            if isinstance(cmd, CommandDefinition):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create CDG command bytes"""
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Build 5-byte command frame
        msg = bytearray([
            0x03,  # Fixed length
            0x00,  # Service command (read/write)
            cmd_def.pid,  # Command PID
            0x00,  # Data byte (if needed)
            0x00  # Checksum (calculated below)
        ])

        # Add parameters if writing
        if params and cmd_def.write:
            msg[1] = 0x10  # Write command
            msg[3] = self._encode_param(params.get('value', 0), cmd_def.param_type)
        else:
            msg[1] = 0x00  # Read command

        # Calculate checksum (sum of bytes 1-3)
        msg[4] = sum(msg[1:4]) & 0xFF

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse CDG response bytes"""
        if len(response) != 9:
            return self._error_response("Invalid response length")

        # Verify start byte
        if response[0] != 0x07:
            return self._error_response("Invalid start byte")

        # Extract fields
        page_no = response[1]
        status = response[2]
        error = response[3]
        pressure_high = response[4]
        pressure_low = response[5]
        read_value = response[6]
        sensor_type = response[7]
        checksum = response[8]

        # Verify checksum
        calc_checksum = sum(response[1:8]) & 0xFF
        if calc_checksum != checksum:
            return self._error_response("Checksum mismatch")

        # Parse status byte
        pressure_unit = (status >> 4) & 0x03
        unit_str = {0: "mbar", 1: "Torr", 2: "Pa"}.get(pressure_unit, "unknown")

        # Calculate pressure value
        pressure_value = ((pressure_high << 8) | pressure_low)
        if pressure_value & 0x8000:  # Handle negative values
            pressure_value = -((~pressure_value + 1) & 0xFFFF)
        pressure = pressure_value / 16384.0  # Scale factor

        return {
            "success": True,
            "pressure": pressure,
            "unit": unit_str,
            "status": {
                "heating": bool(status & 0x80),
                "temp_ok": bool(status & 0x40)
            },
            "errors": self._parse_error_byte(error)
        }

    def _parse_error_byte(self, error: int) -> Dict[str, bool]:
        """Parse error byte into dictionary of error flags"""
        return {
            "sync_error": bool(error & 0x01),
            "invalid_command": bool(error & 0x02),
            "invalid_access": bool(error & 0x04),
            "hardware_error": bool(error & 0x08)
        }

    def _encode_param(self, value: Any, param_type: ParamType) -> int:
        """Encode parameter value based on type"""
        if param_type == ParamType.UINT8:
            return int(value) & 0xFF
        elif param_type == ParamType.UINT16:
            return int(value) & 0xFFFF
        elif param_type == ParamType.FLOAT:
            # Convert float to fixed point
            return int(value * 16384.0) & 0xFFFF
        return 0

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Create error response dictionary"""
        return {
            "success": False,
            "error": message
        }

class PCGProtocol(GaugeProtocol):
    """Protocol implementation for PCG550/PSG550 combination gauges"""

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        super().__init__(address, logger)
        self.device_id = 0x02  # PCG/PSG device ID

    def _initialize_commands(self):
        """Initialize PCG/PSG commands"""
        self._command_defs = {
            "pressure": CommandDefinition(221, "pressure", "Read pressure measurement", True, False),
            "temperature": CommandDefinition(222, "temperature", "Read temperature", True, False),
            "zero_adjust": CommandDefinition(417, "zero_adjust", "Execute zero adjustment", False, True),
            "software_version": CommandDefinition(218, "software_version", "Read software version", True, False),
            "serial_number": CommandDefinition(207, "serial_number", "Read serial number", True, False),
            "error_status": CommandDefinition(228, "error_status", "Read error status", True, False)
        }

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create PCG/PSG command bytes"""
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Create message frame
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,  # Address
            self.device_id,  # Device ID
            0x00,  # ACK bit and message length
            0x05,  # Default message length
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,  # PID MSB
            cmd_def.pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved bytes
        ])

        # Add parameters if writing
        if params and cmd_def.write:
            param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4  # Update message length

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse PCG/PSG response bytes"""
        if len(response) < 7:
            return self._error_response("Response too short")

        # Extract header
        device_id = response[1]
        msg_length = response[3]
        cmd_type = response[4]
        pid = (response[5] << 8) | response[6]

        # Verify device ID
        if device_id != self.device_id:
            return self._error_response("Invalid device ID")

        # Verify message length
        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        # Parse data section
        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """Parse data based on PID"""
        if pid == 221:  # Pressure
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 20))  # Fixs32en20 format
            return {
                "success": True,
                "pressure": pressure,
                "unit": "mbar"
            }
        elif pid == 222:  # Temperature
            temp = struct.unpack('>f', data)[0]
            return {
                "success": True,
                "temperature": temp,
                "unit": "C"
            }
        elif pid == 228:  # Error status
            error_flags = int.from_bytes(data, byteorder='big')
            return {
                "success": True,
                "errors": self._parse_error_flags(error_flags)
            }

        return {"success": True, "raw_data": data.hex()}

    def _parse_error_flags(self, flags: int) -> Dict[str, bool]:
        """Parse error flags into dictionary"""
        return {
            "sensor_error": bool(flags & 0x01),
            "electronics_error": bool(flags & 0x02),
            "calibration_error": bool(flags & 0x04),
            "memory_error": bool(flags & 0x08)
        }


class PPGProtocol(GaugeProtocol):
    """Protocol implementation for PPG550/570 MEMS Pirani & Piezo gauges"""

    def __init__(self, address: int = 254, gauge_type: str = "PPG550", logger: Optional[logging.Logger] = None):
        # Set model-specific attributes before calling super().__init__
        self.gauge_type = gauge_type
        self.has_atm = gauge_type == "PPG570"

        # Now call parent initializer
        super().__init__(address, logger)

        # Initialize command set
        self._initialize_commands()

        self.logger.debug(f"Initialized {self.gauge_type} protocol handler")
        self.logger.debug(f"ATM sensor: {'enabled' if self.has_atm else 'disabled'}")

    def parse_response(self, response: bytes) -> GaugeResponse:
        """Parse response from gauge

        Args:
            response: Raw response bytes from gauge

        Returns:
            GaugeResponse object containing parsed data
        """
        try:
            if not response:
                return GaugeResponse(
                    raw_data=b"",
                    formatted_data="",
                    success=False,
                    error_message="No response received"
                )

            # Decode ASCII response
            resp_str = response.decode('ascii').strip()
            self.logger.debug(f"Parsing response: {resp_str}")

            # Check for error response
            if resp_str.startswith("@NAK"):
                error_msg = resp_str[4:] if len(resp_str) > 4 else "Unknown error"
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=error_msg,
                    success=False,
                    error_message=error_msg
                )

            # Verify response format
            if resp_str.startswith("@ACK"):
                data = resp_str[4:].strip()  # Remove @ACK and any whitespace
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=data,
                    success=True,
                    error_message=None
                )

            # Invalid format
            return GaugeResponse(
                raw_data=response,
                formatted_data=resp_str,
                success=False,
                error_message="Invalid response format"
            )

        except UnicodeDecodeError:
            return GaugeResponse(
                raw_data=response,
                formatted_data=response.hex(),
                success=False,
                error_message="Failed to decode ASCII response"
            )
        except Exception as e:
            self.logger.error(f"Response parse error: {str(e)}")
            return GaugeResponse(
                raw_data=response if response else b"",
                formatted_data="",
                success=False,
                error_message=f"Parse error: {str(e)}"
            )

    def create_command(self, command: GaugeCommand) -> bytes:
        """Create command bytes"""
        try:
            cmd_info = self._command_defs.get(command.name)
            if not cmd_info:
                raise ValueError(f"Unknown command: {command.name}")

            # Build command string
            addr = f"{self.address:03d}" if self.rs485_mode else "254"
            cmd = cmd_info["cmd"]
            cmd_type = "!" if command.command_type in ["write", "!"] else "?"

            # Construct command string
            cmd_str = f"@{addr}{cmd}{cmd_type}"

            # Add parameters for write commands
            if cmd_type == "!" and command.parameters:
                value = command.parameters.get('value')
                if value is not None:
                    cmd_str += str(value)

            # Add terminator
            cmd_str += "\\"

            self.logger.debug(f"Created command: {cmd_str}")
            return cmd_str.encode('ascii')

        except Exception as e:
            self.logger.error(f"Command creation failed: {str(e)}")
            raise

    def test_commands(self) -> List[bytes]:
        """Return list of test commands for connection testing"""
        commands = []

        # Basic commands for both models
        commands.extend([
            self.create_command(GaugeCommand(
                name="software_version",
                command_type="?",
                parameters=None
            )),
            self.create_command(GaugeCommand(
                name="pressure",
                command_type="?",
                parameters=None
            ))
        ])

        # Add ATM sensor test for PPG570
        if self.has_atm:
            commands.append(
                self.create_command(GaugeCommand(
                    name="atm_pressure",
                    command_type="?",
                    parameters=None
                ))
            )

        return commands

    def _initialize_commands(self):
        """Initialize gauge commands based on model"""
        # Common commands for both PPG550 and PPG570
        self._command_defs = {
            "pressure": {
                "cmd": "PR3",
                "type": "read",
                "desc": "Read combined pressure measurement"
            },
            "pirani_pressure": {
                "cmd": "PR1",
                "type": "read",
                "desc": "Read Pirani pressure"
            },
            "piezo_pressure": {
                "cmd": "PR2",
                "type": "read",
                "desc": "Read Piezo pressure"
            },
            "temperature": {
                "cmd": "T",
                "type": "read",
                "desc": "Read temperature"
            },
            "software_version": {
                "cmd": "FV",
                "type": "read",
                "desc": "Read firmware version"
            },
            "serial_number": {
                "cmd": "SN",
                "type": "read",
                "desc": "Read serial number"
            },
            "part_number": {
                "cmd": "PN",
                "type": "read",
                "desc": "Read part number"
            },
            "unit": {
                "cmd": "U",
                "type": "read/write",
                "desc": "Get/set pressure unit (MBAR, PASCAL, TORR)"
            },
            "zero_adjust": {
                "cmd": "VAC",
                "type": "write",
                "desc": "Perform Pirani zero adjustment"
            },
            "piezo_adjust": {
                "cmd": "FS",
                "type": "write",
                "desc": "Perform Piezo full scale adjustment"
            },
            "baud": {
                "cmd": "BAUD",
                "type": "read/write",
                "desc": "Get/set baud rate"
            },
            "address": {
                "cmd": "ADR",
                "type": "read/write",
                "desc": "Get/set device address (RS485)"
            },
            "setpoint_value": {
                "cmd": "SPV",
                "type": "read/write",
                "desc": "Get/set setpoint value"
            },
            "setpoint_enable": {
                "cmd": "SPE",
                "type": "read/write",
                "desc": "Enable/disable setpoint"
            },
            "setpoint_direction": {
                "cmd": "SPD",
                "type": "read/write",
                "desc": "Set setpoint direction (above/below)"
            }
        }

        # Add PPG570-specific commands
        if self.has_atm:
            atm_commands = {
                "atm_pressure": {
                    "cmd": "PR4",
                    "type": "read",
                    "desc": "Read atmospheric pressure"
                },
                "differential_pressure": {
                    "cmd": "PR5",
                    "type": "read",
                    "desc": "Read differential pressure"
                },
                "atm_zero": {
                    "cmd": "ATZ",
                    "type": "write",
                    "desc": "Perform atmospheric sensor zero adjustment"
                },
                "atm_adjust": {
                    "cmd": "ATD",
                    "type": "write",
                    "desc": "Perform atmospheric sensor adjustment"
                }
            }
            self._command_defs.update(atm_commands)

        self.logger.debug(f"Initialized {len(self._command_defs)} commands for {self.gauge_type}")

    @property
    def available_commands(self) -> List[str]:
        """Get list of available commands for current gauge type"""
        return list(self._command_defs.keys())

    def send_command(self, command: GaugeCommand) -> GaugeResponse:
        """Send command to gauge and parse response

        Args:
            command: GaugeCommand object to send

        Returns:
            GaugeResponse object containing parsed response
        """
        try:
            cmd_bytes = self.create_command(command)
            self.logger.debug(f"Sending command: {cmd_bytes.hex()}")

            # Clear any pending data
            if hasattr(self, 'ser') and self.ser:
                self.ser.reset_input_buffer()

            # Send command
            if hasattr(self, 'ser') and self.ser:
                self.ser.write(cmd_bytes)
                self.ser.flush()

                # Read response
                response = self._read_response()
                return self.parse_response(response)
            else:
                return GaugeResponse(
                    raw_data=b"",
                    formatted_data="",
                    success=False,
                    error_message="Serial port not open"
                )

        except Exception as e:
            self.logger.error(f"Command send error: {str(e)}")
            return GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=str(e)
            )

class BPG40xProtocol(GaugeProtocol):
    """Protocol implementation for BPG402 hot cathode gauges"""

    def _initialize_commands(self):
        """Initialize BPG gauge commands"""
        for cmd in vars(BPGCommand).values():
            if isinstance(cmd, CommandDefinition):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create BPG command bytes"""
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Create message frame
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,  # Address
            0x14,  # Device ID for BPG
            0x00,  # ACK bit and message length
            0x05,  # Default message length
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,  # PID MSB
            cmd_def.pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved bytes
        ])

        # Add parameters for write commands
        if params and cmd_def.write:
            param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4  # Update message length

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse BPG response bytes"""
        if len(response) < 7:
            return self._error_response("Response too short")

        # Extract header
        device_id = response[1]
        msg_length = response[3]
        cmd_type = response[4]
        pid = (response[5] << 8) | response[6]

        # Verify device ID
        if device_id != 0x14:
            return self._error_response("Invalid device ID")

        # Verify length
        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        # Parse data based on PID
        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """Parse data section based on PID"""
        if pid == BPGCommand.PRESSURE.pid:
            # Pressure is in LogFixs32en26 format
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {
                "success": True,
                "pressure": pressure,
                "unit": "mbar"
            }
        elif pid == BPGCommand.EMISSION_STATUS.pid:
            status = data[0]
            return {
                "success": True,
                "emission_status": {
                    "enabled": bool(status & 0x01),
                    "emission_on": bool(status & 0x02),
                    "degas_active": bool(status & 0x04)
                }
            }
        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        """Encode parameter value to bytes"""
        if param_type == ParamType.BOOL:
            return bytes([1 if value else 0])
        elif param_type == ParamType.UINT32:
            return value.to_bytes(4, byteorder='big')
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes([0])


class BCG450Protocol(GaugeProtocol):
    """Protocol implementation for BCG450 combination gauges"""

    def _initialize_commands(self):
        """Initialize BCG gauge commands"""
        for cmd in vars(BCG450Command).values():
            if isinstance(cmd, CommandDefinition):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create BCG command bytes"""
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Create message frame similar to BPG but with BCG device ID
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,  # Address
            0x0B,  # Device ID for BCG
            0x00,  # ACK bit and message length
            0x05,  # Default message length
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,  # PID MSB
            cmd_def.pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved bytes
        ])

        # Add parameters for write commands
        if params and cmd_def.write:
            param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4  # Update message length

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

        def parse_response(self, response: bytes) -> Dict[str, Any]:
            """Parse BCG response bytes"""
            if len(response) < 7:
                return self._error_response("Response too short")

            # Extract header
            device_id = response[1]
            msg_length = response[3]
            cmd_type = response[4]
            pid = (response[5] << 8) | response[6]

            # Verify device ID
            if device_id != 0x0B:  # BCG device ID
                return self._error_response("Invalid device ID")

            # Verify length
            if len(response) != msg_length + 6:
                return self._error_response("Invalid message length")

            # Verify CRC
            received_crc = (response[-1] << 8) | response[-2]
            calculated_crc = self.calculate_crc16(response[:-2])
            if received_crc != calculated_crc:
                return self._error_response("CRC mismatch")

            # Parse data based on PID
            data = response[7:-2]
            return self._parse_data(pid, data)

        def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
            """Parse data section based on PID and measurement type"""
            if pid == BCGCommand.PRESSURE.pid:
                # Combined pressure reading from all sensors
                value = int.from_bytes(data, byteorder='big', signed=True)
                pressure = self._convert_to_pressure(value)
                return {
                    "success": True,
                    "pressure": pressure,
                    "unit": "mbar"
                }
            elif pid == BCGCommand.SENSOR_STATUS.pid:
                status = data[0]
                return {
                    "success": True,
                    "sensor_status": {
                        "pirani_active": bool(status & 0x01),
                        "ba_active": bool(status & 0x02),
                        "cdg_active": bool(status & 0x04),
                        "degas_active": bool(status & 0x08)
                    }
                }
            return {"success": True, "raw_data": data.hex()}

        def _convert_to_pressure(self, raw_value: int) -> float:
            """Convert raw sensor value to pressure"""
            # BCG uses LogFixs32en26 format for pressure values
            return 10 ** (raw_value / (2 ** 26))

    class PCGProtocol(GaugeProtocol):
        """Protocol implementation for PCG550/PSG550 combination gauges"""

        def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
            super().__init__(address, logger)
            self.device_id = 0x02  # PCG/PSG device ID

        def _initialize_commands(self):
            """Initialize PCG/PSG commands"""
            self._command_defs = {
                "pressure": CommandDefinition(221, "pressure", "Read pressure measurement", True, False),
                "temperature": CommandDefinition(222, "temperature", "Read temperature", True, False),
                "zero_adjust": CommandDefinition(417, "zero_adjust", "Execute zero adjustment", False, True),
                "software_version": CommandDefinition(218, "software_version", "Read software version", True, False),
                "serial_number": CommandDefinition(207, "serial_number", "Read serial number", True, False),
                "error_status": CommandDefinition(228, "error_status", "Read error status", True, False)
            }

        def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
            """Create PCG/PSG command bytes"""
            cmd_def = self._command_defs.get(command)
            if not cmd_def:
                raise ValueError(f"Unknown command: {command}")

            # Create message frame
            msg = bytearray([
                0x00 if not self.rs485_mode else self.address,  # Address
                self.device_id,  # Device ID
                0x00,  # ACK bit and message length
                0x05,  # Default message length
                0x01 if cmd_def.read else 0x03,  # Command type
                (cmd_def.pid >> 8) & 0xFF,  # PID MSB
                cmd_def.pid & 0xFF,  # PID LSB
                0x00, 0x00  # Reserved bytes
            ])

            # Add parameters if writing
            if params and cmd_def.write:
                param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
                msg.extend(param_bytes)
                msg[3] = len(msg) - 4  # Update message length

            # Calculate and append CRC
            crc = self.calculate_crc16(msg)
            msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

            return bytes(msg)

        def parse_response(self, response: bytes) -> Dict[str, Any]:
            """Parse PCG/PSG response bytes"""
            if len(response) < 7:
                return self._error_response("Response too short")

            # Extract header
            device_id = response[1]
            msg_length = response[3]
            cmd_type = response[4]
            pid = (response[5] << 8) | response[6]

            # Verify device ID
            if device_id != self.device_id:
                return self._error_response("Invalid device ID")

            # Verify message length
            if len(response) != msg_length + 6:
                return self._error_response("Invalid message length")

            # Verify CRC
            received_crc = (response[-1] << 8) | response[-2]
            calculated_crc = self.calculate_crc16(response[:-2])
            if received_crc != calculated_crc:
                return self._error_response("CRC mismatch")

            # Parse data section
            data = response[7:-2]
            return self._parse_data(pid, data)

        def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
            """Parse data based on PID"""
            if pid == 221:  # Pressure
                value = int.from_bytes(data, byteorder='big', signed=True)
                pressure = 10 ** (value / (2 ** 20))  # Fixs32en20 format
                return {
                    "success": True,
                    "pressure": pressure,
                    "unit": "mbar"
                }
            elif pid == 222:  # Temperature
                temp = struct.unpack('>f', data)[0]
                return {
                    "success": True,
                    "temperature": temp,
                    "unit": "C"
                }
            elif pid == 228:  # Error status
                error_flags = int.from_bytes(data, byteorder='big')
                return {
                    "success": True,
                    "errors": self._parse_error_flags(error_flags)
                }

            return {"success": True, "raw_data": data.hex()}

        def _parse_error_flags(self, flags: int) -> Dict[str, bool]:
            """Parse error flags into dictionary"""
            return {
                "sensor_error": bool(flags & 0x01),
                "electronics_error": bool(flags & 0x02),
                "calibration_error": bool(flags & 0x04),
                "memory_error": bool(flags & 0x08)
            }

    class OPGProtocol(GaugeProtocol):
        """Protocol implementation for OPG550 optical plasma gauge"""

        def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
            super().__init__(address, logger)
            self.device_id = 0x0B  # OPG device ID

        def _initialize_commands(self):
            """Initialize OPG commands"""
            self._command_defs = {
                "pressure": CommandDefinition(14000, "pressure", "Read total pressure", True, False),
                "plasma_status": CommandDefinition(12003, "plasma_status", "Get plasma status", True, False),
                "plasma_control": CommandDefinition(12002, "plasma_control", "Control plasma", False, True),
                "self_test": CommandDefinition(11000, "self_test", "Get self diagnostic status", True, False),
                "error_status": CommandDefinition(11002, "error_status", "Get number of errors", True, False),
                "software_version": CommandDefinition(10004, "software_version", "Get firmware version", True, False)
            }

        def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
            """Create OPG command bytes"""
            cmd_def = self._command_defs.get(command)
            if not cmd_def:
                raise ValueError(f"Unknown command: {command}")

            # Create message frame
            msg = bytearray([
                0x00,  # Address (RS232 only for OPG)
                self.device_id,  # Device ID
                0x20,  # Header with protocol version 2
                0x00,  # Message length MSB
                0x05,  # Message length LSB
                0x01 if cmd_def.read else 0x03,  # Command type
                (cmd_def.pid >> 8) & 0xFF,  # PID MSB
                cmd_def.pid & 0xFF,  # PID LSB
                0x00, 0x00  # Index bytes
            ])

            # Add parameters if writing
            if params and cmd_def.write:
                param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
                msg.extend(param_bytes)
                msg[3:5] = len(msg[5:]).to_bytes(2, byteorder='big')

            # Calculate and append CRC
            crc = self.calculate_crc16(msg)
            msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

            return bytes(msg)

        def parse_response(self, response: bytes) -> Dict[str, Any]:
            """Parse OPG response bytes"""
            if len(response) < 11:  # Minimum response length
                return self._error_response("Response too short")

            # Extract header
            device_id = response[1]
            protocol_ver = (response[2] >> 4) & 0x0F
            msg_length = (response[3] << 8) | response[4]
            cmd_type = response[5]
            pid = (response[6] << 8) | response[7]

            # Basic validation
            if device_id != self.device_id:
                return self._error_response("Invalid device ID")
            if protocol_ver != 2:
                return self._error_response("Invalid protocol version")
            if len(response) != msg_length + 11:
                return self._error_response("Invalid message length")

            # Verify CRC
            received_crc = (response[-1] << 8) | response[-2]
            calculated_crc = self.calculate_crc16(response[:-2])
            if received_crc != calculated_crc:
                return self._error_response("CRC mismatch")

            # Parse data section
            data = response[10:-2]  # Skip header and index bytes
            return self._parse_data(pid, data)

        def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
            """Parse data based on PID"""
            if pid == 14000:  # Total pressure
                pressure = struct.unpack('>f', data)[0]
                return {
                    "success": True,
                    "pressure": pressure,
                    "unit": "mbar"
                }
            elif pid == 12003:  # Plasma status
                status = data[0]
                return {
                    "success": True,
                    "plasma_status": {
                        "off": status == 0,
                        "striking": status == 1,
                        "on": status == 2
                    }
                }
            elif pid == 11000:  # Self diagnostic
                status = data[0]
                return {
                    "success": True,
                    "diagnostic": {
                        "ok": status == 0,
                        "service_needed": status == 1,
                        "failure": status == 2
                    }
                }

            return {"success": True, "raw_data": data.hex()}

    def get_protocol(gauge_type: str, address: int = 254) -> GaugeProtocol:
        """Factory function to get appropriate protocol handler"""
        protocols = {
            "CDG025D": CDGProtocol,
            "CDG045D": CDGProtocol,
            "PCG550": PCGProtocol,
            "PSG550": PCGProtocol,
            "BPG402": BPGProtocol,
            "BCG450": BCGProtocol,
            "OPG550": OPGProtocol
        }

        protocol_class = protocols.get(gauge_type)
        if not protocol_class:
            raise ValueError(f"Unsupported gauge type: {gauge_type}")

        return protocol_class(address=address)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse BCG response bytes"""
        if len(response) < 7:
            return self._error_response("Response too short")

        # Extract header
        device_id = response[1]
        msg_length = response[3]
        cmd_type = response[4]
        pid = (response[5] << 8) | response[6]

        # Verify device ID
        if device_id != 0x0B:  # BCG device ID
            return self._error_response("Invalid device ID")

        # Verify length
        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        # Parse data based on PID
        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """Parse data section based on PID and measurement type"""
        if pid == BCGCommand.PRESSURE.pid:
            # Combined pressure reading from all sensors
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = self._convert_to_pressure(value)
            return {
                "success": True,
                "pressure": pressure,
                "unit": "mbar"
            }
        elif pid == BCGCommand.SENSOR_STATUS.pid:
            status = data[0]
            return {
                "success": True,
                "sensor_status": {
                    "pirani_active": bool(status & 0x01),
                    "ba_active": bool(status & 0x02),
                    "cdg_active": bool(status & 0x04),
                    "degas_active": bool(status & 0x08)
                }
            }
        return {"success": True, "raw_data": data.hex()}

    def _convert_to_pressure(self, raw_value: int) -> float:
        """Convert raw sensor value to pressure"""
        # BCG uses LogFixs32en26 format for pressure values
        return 10 ** (raw_value / (2 ** 26))


class BPG552Protocol(GaugeProtocol):
    """Protocol implementation for BPG552 DualGauge"""

    def _initialize_commands(self):
        """Initialize BPG552 gauge commands"""
        for cmd in vars(BPG552Command).values():
            if isinstance(cmd, CommandDefinition):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create BPG552 command bytes

        Args:
            command: Command name
            params: Optional command parameters

        Returns:
            Command frame as bytes
        """
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Create message frame
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,  # Address
            0x14,  # Device ID for BPG
            0x00,  # ACK bit and message length
            0x05,  # Default message length
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,  # PID MSB
            cmd_def.pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved bytes
        ])

        # Add parameters for write commands
        if params and cmd_def.write:
            param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4  # Update message length

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse BPG552 response bytes

        Args:
            response: Response frame bytes

        Returns:
            Dictionary containing parsed response data
        """
        if len(response) < 7:
            return self._error_response("Response too short")

        # Extract header fields
        device_id = response[1]
        msg_length = response[3]
        cmd_type = response[4]
        pid = (response[5] << 8) | response[6]

        # Verify device ID (0x14 for BPG)
        if device_id != 0x14:
            return self._error_response("Invalid device ID")

        # Verify message length
        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        # Parse data based on PID
        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """Parse data based on parameter ID

        Args:
            pid: Parameter ID
            data: Response data bytes

        Returns:
            Dictionary containing parsed data
        """
        if pid == BPG552Command.PRESSURE.pid:
            # Pressure is in LogFixs32en26 format
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {
                "success": True,
                "pressure": pressure,
                "unit": "mbar"
            }

        elif pid == BPG552Command.TEMPERATURE.pid:
            # Temperature as 32-bit float
            temp = struct.unpack('>f', data)[0]
            return {
                "success": True,
                "temperature": temp,
                "unit": "C"
            }

        elif pid == BPG552Command.EMISSION_STATUS.pid:
            status = data[0]
            return {
                "success": True,
                "emission_status": {
                    "enabled": bool(status & 0x01),
                    "emission_on": bool(status & 0x02),
                    "degas_active": bool(status & 0x04)
                }
            }

        elif pid == BPG552Command.ERROR_STATUS.pid:
            error_flags = int.from_bytes(data, byteorder='big')
            return {
                "success": True,
                "errors": {
                    "sensor_error": bool(error_flags & 0x01),
                    "electronics_error": bool(error_flags & 0x02),
                    "calibration_error": bool(error_flags & 0x04),
                    "memory_error": bool(error_flags & 0x08)
                }
            }

        # Return raw data for unknown PIDs
        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        """Encode parameter value based on type"""
        if param_type == ParamType.BOOL:
            return bytes([1 if value else 0])
        elif param_type == ParamType.UINT32:
            return value.to_bytes(4, byteorder='big')
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes([0])

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Create error response dictionary"""
        self.logger.error(message)
        return {
            "success": False,
            "error": message
        }

class BCG552Protocol(GaugeProtocol):
    """Protocol implementation for BCG552 TripleGauge"""

    def _initialize_commands(self):
        """Initialize BCG552 gauge commands"""
        for cmd in vars(BCG552Command).values():
            if isinstance(cmd, CommandDefinition):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create BCG552 command bytes

        Args:
            command: Command name
            params: Optional command parameters

        Returns:
            Command frame as bytes
        """
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Build message frame
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,  # Address
            0x02,  # Device ID for BCG552
            0x00,  # ACK bit and message length
            0x05,  # Default message length
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,  # PID MSB
            cmd_def.pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved bytes
        ])

        # Add parameters if writing
        if params and cmd_def.write:
            param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4  # Update message length

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse BCG552 response bytes

        Args:
            response: Response frame bytes

        Returns:
            Dictionary containing parsed response data
        """
        if len(response) < 7:
            return self._error_response("Response too short")

        # Extract header
        device_id = response[1]
        msg_length = response[3]
        cmd_type = response[4]
        pid = (response[5] << 8) | response[6]

        # Verify response
        if device_id != 0x02:
            return self._error_response("Invalid device ID")

        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        # Parse data section
        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """Parse data based on parameter ID

        Args:
            pid: Parameter ID
            data: Response data bytes

        Returns:
            Dictionary containing parsed data
        """
        if pid == 221:  # Pressure
            # Convert from LogFixs32en26 format
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {
                "success": True,
                "pressure": pressure,
                "unit": "mbar"
            }
        elif pid == 222:  # Temperature
            temp = struct.unpack('>f', data)[0]
            return {
                "success": True,
                "temperature": temp,
                "unit": "C"
            }
        elif pid == 228:  # Error status
            error_flags = int.from_bytes(data, byteorder='big')
            return {
                "success": True,
                "errors": {
                    "sensor_error": bool(error_flags & 0x01),
                    "electronics_error": bool(error_flags & 0x02),
                    "calibration_error": bool(error_flags & 0x04),
                    "memory_error": bool(error_flags & 0x08)
                }
            }

        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        """Encode parameter value based on type"""
        if param_type == ParamType.UINT8:
            return bytes([int(value) & 0xFF])
        elif param_type == ParamType.UINT16:
            return int(value).to_bytes(2, byteorder='big')
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes([0])

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Create error response dictionary"""
        self.logger.error(message)
        return {
            "success": False,
            "error": message
        }

class MAGMPGProtocol(GaugeProtocol):
    """Protocol implementation for MAG500 and MPG500 gauges"""

    def __init__(self, device_id: int = 0x14, address: int = 254, logger: Optional[logging.Logger] = None):
        """Initialize protocol handler

        Args:
            device_id: Device ID (0x14 for MAG500, 0x04 for MPG500)
            address: Device address for RS485 mode
            logger: Optional logger instance
        """
        super().__init__(address, logger)
        self.device_id = device_id
        self._initialize_commands()

    def _initialize_commands(self):
        """Initialize gauge commands based on device ID"""
        command_class = MAG500Command if self.device_id == 0x14 else MPG500Command
        for cmd in vars(command_class).values():
            if isinstance(cmd, CommandDefinition):
                self._command_defs[cmd.name] = cmd

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create command bytes

        Args:
            command: Command name
            params: Optional command parameters

        Returns:
            Command frame as bytes
        """
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Create message frame
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,  # Address
            self.device_id,  # Device ID (0x14 for MAG500, 0x04 for MPG500)
            0x00,  # ACK bit and message length
            0x05,  # Default message length
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,  # PID MSB
            cmd_def.pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved bytes
        ])

        # Add parameters for write commands
        if params and cmd_def.write:
            param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3] = len(msg) - 4  # Update message length

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse response frame

        Args:
            response: Raw response bytes

        Returns:
            Dictionary containing parsed response data
        """
        if len(response) < 7:
            return self._error_response("Response too short")

        # Extract header fields
        device_id = response[1]
        msg_length = response[3]
        cmd_type = response[4]
        pid = (response[5] << 8) | response[6]

        # Verify device ID
        if device_id != self.device_id:
            return self._error_response("Invalid device ID")

        # Verify length
        if len(response) != msg_length + 6:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        # Parse data section
        data = response[7:-2]
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """Parse data based on parameter ID

        Args:
            pid: Parameter ID
            data: Response data bytes

        Returns:
            Dictionary containing parsed data
        """
        if pid == 221:  # Pressure
            # Convert from LogFixs32en26 format
            value = int.from_bytes(data, byteorder='big', signed=True)
            pressure = 10 ** (value / (2 ** 26))
            return {
                "success": True,
                "pressure": pressure,
                "unit": "mbar"
            }

        elif pid == 222:  # Temperature
            temp = struct.unpack('>f', data)[0]
            return {
                "success": True,
                "temperature": temp,
                "unit": "C"
            }

        elif pid == 223:  # Active sensor (MPG500 only)
            status = data[0]
            return {
                "success": True,
                "active_sensor": {
                    "ccig": bool(status & 0x01),
                    "pirani": bool(status & 0x02),
                    "mixed": bool(status & 0x04)
                }
            }

        elif pid == 533:  # CCIG status (MAG500 only)
            status = data[0]
            return {
                "success": True,
                "ccig_status": {
                    "off": status == 0,
                    "on_not_ignited": status == 1,
                    "on_ignited": status == 3
                }
            }

        elif pid == 228:  # Error status
            error_flags = int.from_bytes(data, byteorder='big')
            return {
                "success": True,
                "errors": {
                    "no_error": error_flags == 0,
                    "eeprom_timeout": bool(error_flags & 0x01),
                    "eeprom_crc": bool(error_flags & 0x02),
                    "eeprom_error": bool(error_flags & 0x04),
                    "pirani_filament": bool(error_flags & 0x08),
                    "ccig_short": bool(error_flags & 0x800)
                }
            }

        elif pid == 104:  # Run hours
            hours = int.from_bytes(data, byteorder='big') * 0.25  # Convert to hours
            return {
                "success": True,
                "run_hours": hours
            }

        # Return raw data for unknown PIDs
        return {"success": True, "raw_data": data.hex()}

    def _encode_param(self, value: Any, param_type: ParamType) -> bytes:
        """Encode parameter value based on type"""
        if param_type == ParamType.BOOL:
            return bytes([1 if value else 0])
        elif param_type == ParamType.UINT32:
            return value.to_bytes(4, byteorder='big')
        elif param_type == ParamType.FLOAT:
            return struct.pack('>f', float(value))
        return bytes([0])

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Create error response dictionary"""
        self.logger.error(message)
        return {
            "success": False,
            "error": message
        }

class OPGProtocol(GaugeProtocol):
    """Protocol implementation for OPG550 optical plasma gauge"""

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        super().__init__(address, logger)
        self.device_id = 0x0B  # OPG device ID

    def _initialize_commands(self):
        """Initialize OPG commands"""
        self._command_defs = {
            "pressure": CommandDefinition(14000, "pressure", "Read total pressure", True, False),
            "plasma_status": CommandDefinition(12003, "plasma_status", "Get plasma status", True, False),
            "plasma_control": CommandDefinition(12002, "plasma_control", "Control plasma", False, True),
            "self_test": CommandDefinition(11000, "self_test", "Get self diagnostic status", True, False),
            "error_status": CommandDefinition(11002, "error_status", "Get number of errors", True, False),
            "software_version": CommandDefinition(10004, "software_version", "Get firmware version", True, False)
        }

    def create_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Create OPG command bytes"""
        cmd_def = self._command_defs.get(command)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command}")

        # Create message frame
        msg = bytearray([
            0x00,  # Address (RS232 only for OPG)
            self.device_id,  # Device ID
            0x20,  # Header with protocol version 2
            0x00,  # Message length MSB
            0x05,  # Message length LSB
            0x01 if cmd_def.read else 0x03,  # Command type
            (cmd_def.pid >> 8) & 0xFF,  # PID MSB
            cmd_def.pid & 0xFF,  # PID LSB
            0x00, 0x00  # Index bytes
        ])

        # Add parameters if writing
        if params and cmd_def.write:
            param_bytes = self._encode_param(params.get('value', 0), cmd_def.param_type)
            msg.extend(param_bytes)
            msg[3:5] = len(msg[5:]).to_bytes(2, byteorder='big')

        # Calculate and append CRC
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """Parse OPG response bytes"""
        if len(response) < 11:  # Minimum response length
            return self._error_response("Response too short")

        # Extract header
        device_id = response[1]
        protocol_ver = (response[2] >> 4) & 0x0F
        msg_length = (response[3] << 8) | response[4]
        cmd_type = response[5]
        pid = (response[6] << 8) | response[7]

        # Basic validation
        if device_id != self.device_id:
            return self._error_response("Invalid device ID")
        if protocol_ver != 2:
            return self._error_response("Invalid protocol version")
        if len(response) != msg_length + 11:
            return self._error_response("Invalid message length")

        # Verify CRC
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return self._error_response("CRC mismatch")

        # Parse data section
        data = response[10:-2]  # Skip header and index bytes
        return self._parse_data(pid, data)

    def _parse_data(self, pid: int, data: bytes) -> Dict[str, Any]:
        """Parse data based on PID"""
        if pid == 14000:  # Total pressure
            pressure = struct.unpack('>f', data)[0]
            return {
                "success": True,
                "pressure": pressure,
                "unit": "mbar"
            }
        elif pid == 12003:  # Plasma status
            status = data[0]
            return {
                "success": True,
                "plasma_status": {
                    "off": status == 0,
                    "striking": status == 1,
                    "on": status == 2
                }
            }
        elif pid == 11000:  # Self diagnostic
            status = data[0]
            return {
                "success": True,
                "diagnostic": {
                    "ok": status == 0,
                    "service_needed": status == 1,
                    "failure": status == 2
                }
            }

        return {"success": True, "raw_data": data.hex()}

def get_protocol(gauge_type: str, address: int = 254) -> GaugeProtocol:
    """Factory function to get appropriate protocol handler"""
    protocols = {
        "CDG025D": CDGProtocol,
        "CDG045D": CDGProtocol,
        "PSG550": PCGProtocol,
        "PCG550": PCGProtocol,
        "PPG550": PPGProtocol,
        "PPG570": PPGProtocol,
        "MAG500": MAGMPGProtocol,
        "MPG500": MAGMPGProtocol,
        "OPG550": OPGProtocol,
        "BPG402": BPG40xProtocol,
        "BPG552": BPG552Protocol,
        "BCG450": BCG450Protocol,
        "BCG552": BCG552Protocol
    }

    protocol_class = protocols.get(gauge_type)
    if not protocol_class:
        raise ValueError(f"Unsupported gauge type: {gauge_type}")

    return protocol_class(address=address)