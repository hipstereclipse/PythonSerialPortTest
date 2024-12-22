"""
response_handler.py
Defines the ResponseHandler class for formatting raw bytes into different output styles.
"""

from ..models import GaugeResponse   # Imports the standard GaugeResponse data structure


class ResponseHandler:
    """
    Handles formatting and processing of gauge responses, especially for different output formats.
    It can also parse specialized frames for certain gauge families.
    """

    def __init__(self, output_format: str = "ASCII"):
        """
        Initializes with a desired default output format for displayed data.
        """
        self.output_format = output_format

    def format_response(self, response: bytes) -> str:
        """
        Converts the given bytes to a string according to the current output_format.
        Valid formats: Hex, Binary, ASCII, UTF-8, Decimal, or Raw Bytes.
        """
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
            else:
                # If "Raw Bytes" or unrecognized, represent as raw Python bytes
                return str(response)
        except Exception as e:
            return f"Error formatting response: {str(e)}"

    def suggest_format(self, raw_response: bytes) -> str:
        """
        Suggests the best output format based on the content of raw_response.
        Similar logic to IntelligentCommandSender but for responses.
        """
        if not raw_response:
            return "Hex"

        try:
            decoded = raw_response.decode('ascii')
            # If all printable ASCII, suggests ASCII
            if all(32 <= ord(c) <= 126 or c in '\r\n' for c in decoded):
                return "ASCII"
        except:
            pass

        if any(b > 127 for b in raw_response):
            return "Hex"

        if all(b < 100 for b in raw_response):
            return "Decimal"

        return "Hex"

    def set_output_format(self, format_type: str):
        """
        Updates the output format for subsequent calls.
        """
        self.output_format = format_type

    def process_cdg_frame(self, response: bytes) -> dict:
        """
        Example method to process a 9-byte frame from CDG gauges.
        Extracts fields like pressure, status, etc.
        Returns a dictionary or an error if anything is malformed.
        """
        if len(response) != 9:
            return {"error": "Invalid frame length"}

        try:
            return {
                "start_byte": response[0],
                "page_no": response[1],
                "status": {
                    "unit": (response[2] >> 4) & 0x03,
                    "heating": bool(response[2] & 0x80),
                    "temp_ok": bool(response[2] & 0x40),
                    "emission": bool(response[2] & 0x20),
                },
                "error": response[3],
                "pressure": self._calculate_cdg_pressure(response[4], response[5]),
                "read_value": response[6],
                "sensor_type": response[7],
                "checksum": response[8],
                "checksum_valid": self._verify_cdg_checksum(response),
            }
        except Exception as e:
            return {"error": f"Frame processing error: {str(e)}"}

    def _calculate_cdg_pressure(self, high_byte: int, low_byte: int) -> float:
        """
        Interprets two bytes as a signed 16-bit fixed-point for pressure.
        The gauge often uses 14 bits for fractional part => divides by 2^14 (16384).
        """
        pressure_value = (high_byte << 8) | low_byte
        if pressure_value & 0x8000:
            pressure_value = -((~pressure_value + 1) & 0xFFFF)
        return pressure_value / 16384.0

    def _verify_cdg_checksum(self, frame: bytes) -> bool:
        """
        For a 9-byte CDG frame, sums bytes 1..7 and checks if it matches byte 8.
        """
        if len(frame) != 9:
            return False
        calc_checksum = sum(frame[1:8]) & 0xFF
        return calc_checksum == frame[8]

    def parse_ppg_response(self, response: bytes) -> dict:
        """
        Example parser for ASCII responses from PPG gauges.
        Typically starts with '@ACK' or '@NAK' and ends with ';FF'.
        """
        try:
            decoded = response.decode('ascii').strip()
            if not decoded.startswith('@') or not decoded.endswith(';FF'):
                return {"error": "Invalid response format"}

            if decoded.startswith('@ACK'):
                data = decoded[4:-3]  # Removes '@ACK' and ';FF'
            elif decoded.startswith('@NAK'):
                return {"error": f"Command failed: {decoded[4:-3]}"}
            else:
                data = decoded[1:-3]  # Removes '@' and ';FF'

            return {
                "data": data,
                "values": data.split(',') if ',' in data else [data]
            }
        except Exception as e:
            return {"error": f"Parse error: {str(e)}"}

    def create_gauge_response(
        self,
        raw_data: bytes,
        formatted_data: str = "",
        success: bool = True,
        error_message: str = None
    ) -> GaugeResponse:
        """
        Builds a standardized GaugeResponse object, optionally formatting raw data if needed.
        """
        return GaugeResponse(
            raw_data=raw_data,
            formatted_data=formatted_data or self.format_response(raw_data),
            success=success,
            error_message=error_message
        )
