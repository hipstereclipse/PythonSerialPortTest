import serial
import serial.tools.list_ports
from typing import Optional, List, Tuple
import time
import logging
from serial_gauge.protocols import *
from serial_gauge.models import *
from serial_gauge.config import *
import binascii

def get_protocol(gauge_type: str, device_id: int = 0x02) -> GaugeProtocol:
    """Factory function to get the appropriate protocol handler"""
    if gauge_type == "PPG550":
        return PPG550Protocol()
    elif gauge_type == "PCG550":
        return PCG550Protocol(device_id)
    elif gauge_type == "PSG550":
        return PCG550Protocol(device_id)
    elif gauge_type == "MAG500":
        return MAGMPGProtocol(device_id)  # Device ID will be 0x14 (20)
    elif gauge_type == "MPG500":
        return MAGMPGProtocol(device_id)  # Device ID will be 0x04 (4)
    else:
        raise ValueError(f"Unsupported gauge type: {gauge_type}")

class GaugeCommunicator:
    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        self.port = port
        self.gauge_type = gauge_type
        self.logger = logger or logging.getLogger(__name__)
        self.ser: Optional[serial.Serial] = None

        # Set up protocol based on gauge type
        params = GAUGE_PARAMETERS[gauge_type]
        self.protocol = get_protocol(gauge_type, params.get("device_id", 0x02))

        self.baudrate = params["baudrate"]
        self.commands = params["commands"]
        self.output_format = "ASCII"

        # Default serial settings
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_ONE
        self.timeout = 2  # Increased timeout
        self.write_timeout = 2

    def format_response(self, response: bytes) -> str:
        """Format response according to selected output format"""
        if not response:
            return "No response"

        try:
            if self.output_format == "Hex":
                return ' '.join(f'{byte:02x}' for byte in response)
            elif self.output_format == "Binary":
                return ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in response)
            elif self.output_format == "ASCII":
                return response.decode('ascii', errors='replace')
            elif self.output_format == "UTF-8":
                return response.decode('utf-8', errors='replace')
            elif self.output_format == "Decimal":
                return ' '.join(str(byte) for byte in response)
            else:  # Raw Bytes
                return str(response)
        except Exception as e:
            return f"Error formatting response: {str(e)}"

    def set_output_format(self, format_type: str):
        """Set the output format type"""
        self.output_format = format_type

    def connect(self) -> bool:
        """Establish connection to the gauge with improved handshaking"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                write_timeout=self.write_timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )

            # Set initial line states
            self.ser.setDTR(True)
            self.ser.setRTS(True)
            time.sleep(0.2)  # Wait for lines to settle

            # Clear any pending data
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Try test commands with proper delays
            test_commands = self.protocol.test_commands()
            for cmd_bytes in test_commands:
                self.logger.debug(f"Testing connection with: {' '.join(f'{b:02x}' for b in cmd_bytes)}")

                # Toggle RTS before sending
                self.ser.setRTS(False)
                time.sleep(0.01)
                self.ser.setRTS(True)

                self.ser.write(cmd_bytes)
                self.ser.flush()
                time.sleep(0.3)  # Longer wait for response

                if self.ser.in_waiting:
                    response = self.read_response()
                    if response:
                        self.logger.debug(f"Got response: {' '.join(f'{b:02x}' for b in response)}")
                        return True

                # Clear buffers between attempts
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.2)

            self.logger.debug("No response to test commands")
            return False

        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            if self.ser and self.ser.is_open:
                self.ser.close()
            return False

    def disconnect(self):
        """Close the serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

    def test_enq(self) -> bool:
        """Test basic communication with ENQ"""
        if not self.ser or not self.ser.is_open:
            return False

        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Send ENQ (0x05)
            self.ser.write(b'\x05')
            self.ser.flush()
            time.sleep(0.1)  # Wait for response

            if self.ser.in_waiting:
                response = self.ser.read(self.ser.in_waiting)
                self.logger.debug(f"ENQ response: {' '.join(f'{b:02x}' for b in response)}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"ENQ test failed: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """Test if connection is working"""
        if not self.ser or not self.ser.is_open:
            return False

        try:
            # Get test commands
            test_commands = self.protocol.test_commands()

            for cmd_bytes in test_commands:
                self.logger.debug(f"Trying command: {' '.join(f'{b:02x}' for b in cmd_bytes)}")

                # Clear buffers
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()

                # Send command
                self.ser.write(cmd_bytes)
                self.ser.flush()
                time.sleep(0.2)  # Wait a bit longer for response

                # Check for response
                if self.ser.in_waiting:
                    response = self.read_response()
                    if response:
                        self.logger.debug(f"Got response: {' '.join(f'{b:02x}' for b in response)}")
                        return True
                else:
                    self.logger.debug("No response received")

            return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def send_command(self, command: GaugeCommand) -> GaugeResponse:
        """Send command with improved debug output"""
        if not self.ser or not self.ser.is_open:
            return GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message="Not connected"
            )

        try:
            # Clear buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Create command
            cmd_bytes = self.protocol.create_command(command)

            # For better debug readability
            if all(32 <= b <= 126 for b in cmd_bytes):  # If all bytes are printable ASCII
                self.logger.debug(f"Sending ASCII command: {cmd_bytes.decode('ascii')}")
                self.logger.debug(f"Hex representation: {' '.join(f'{b:02x}' for b in cmd_bytes)}")
            else:
                self.logger.debug(f"Sending binary command: {' '.join(f'{b:02x}' for b in cmd_bytes)}")

            # Send command
            self.ser.write(cmd_bytes)
            self.ser.flush()
            time.sleep(0.2)

            # Read with timeout
            response = self.read_response()

            if response:
                # For better debug readability
                if all(32 <= b <= 126 for b in response):  # If all bytes are printable ASCII
                    self.logger.debug(f"Received ASCII response: {response.decode('ascii')}")
                    self.logger.debug(f"Hex representation: {' '.join(f'{b:02x}' for b in response)}")
                else:
                    self.logger.debug(f"Received binary response: {' '.join(f'{b:02x}' for b in response)}")

                parsed = self.protocol.parse_response(response)
                if parsed.success:
                    self.logger.debug(f"Parsed response: {parsed.formatted_data}")
                return parsed
            else:
                self.logger.debug("No response received")
                return GaugeResponse(
                    raw_data=b"",
                    formatted_data="",
                    success=False,
                    error_message="No response"
                )

        except Exception as e:
            self.logger.error(f"Command failed: {str(e)}")
            return GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=str(e)
            )

    def send_manual_command(self, command_hex: str):
        """
        Send a manual command (hex string) to the RS232 port and print any response.
        This bypasses device connection check and allows testing command structure.
        :param command_hex: Hexadecimal string representing the command frame.
        """
        try:
            # Convert the hex string to bytes
            command_bytes = bytearray(binascii.unhexlify(command_hex))

            # Write the command to the RS232 port
            self.ser.write(command_bytes)
            print(f"Sent command: {command_hex}")

            # Attempt to read any response, printing even partial or unexpected data
            response = self.ser.read(64)  # Adjust size as needed for testing
            if response:
                print(f"Received response: {binascii.hexlify(response).decode('utf-8')}")
            else:
                print("No response received.")

        except binascii.Error as e:
            print(f"Error in command format: {e}")
        except Exception as e:
            print(f"Error during communication: {e}")

    def try_all_baud_rates(self):
        """Test connection with different baud rates"""
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None

        self.log_message("\n=== Testing Baud Rates ===")

        # Try each baud rate with multiple test commands
        for baud in [9600, 19200, 38400, 57600,115200]:
            self.log_message(f"\nTrying baud rate: {baud}")
            try:
                # Create temporary communicator
                temp_communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )
                temp_communicator.baudrate = baud

                # Try to connect
                if temp_communicator.connect():
                    self.log_message(f"Successfully connected at {baud} baud!")

                    # Try a few commands to verify connection
                    for cmd_name in ["product_name", "software_version", "device_exception"]:
                        cmd = GaugeCommand(
                            name=cmd_name,
                            command_type="?",
                            parameters=temp_communicator.commands[cmd_name]
                        )

                        response = temp_communicator.send_command(cmd)
                        if response.success:
                            self.log_message(f"{cmd_name}: {response.formatted_data}")

                    # Update the UI settings
                    self.serial_frame.baud_var.set(str(baud))
                    self.apply_serial_settings({
                        'baudrate': baud,
                        'bytesize': 8,
                        'parity': 'N',
                        'stopbits': 1.0
                    })

                    temp_communicator.disconnect()
                    return True

                if temp_communicator:
                    temp_communicator.disconnect()

            except Exception as e:
                self.log_message(f"Failed at {baud} baud: {str(e)}")

            time.sleep(1.0)  # Longer delay between attempts

        self.log_message("\nFailed to connect at any baud rate")
        return False

    def read_response(self) -> Optional[bytes]:
        """Read response from serial port with proper timeout handling"""
        if not self.ser:
            return None

        try:
            raw_response = b''
            start_time = time.time()

            # Wait for initial data
            while (time.time() - start_time) < self.ser.timeout:
                if self.ser.in_waiting:
                    break
                time.sleep(0.01)

            if not self.ser.in_waiting:
                return None

            # Read header (first 4 bytes)
            header = self.ser.read(4)
            if len(header) < 4:
                return None

            # Get expected message length from header
            msg_length = header[3]
            remaining_length = msg_length + 2  # Add 2 for CRC

            # Read rest of message
            remaining = self.ser.read(remaining_length)

            return header + remaining

        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return None