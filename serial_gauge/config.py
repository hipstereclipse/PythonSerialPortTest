import logging
from typing import Dict, Any

import serial

# Configuration constants
GAUGE_PARAMETERS = {
    "PCG550": {
        "baudrate": 57600,
        "device_id": 0x02,
        "commands": {
            "pressure": {"pid": 221, "cmd": 1, "desc": "Read pressure (Fixs32en20)"},
            "temperature": {"pid": 222, "cmd": 1, "desc": "Read temperature"},
            "serial_number": {"pid": 207, "cmd": 1, "desc": "Read serial number"},
            "product_name": {"pid": 208, "cmd": 1, "desc": "Read product name"},
            "software_version": {"pid": 218, "cmd": 1, "desc": "Read software version"},
            "device_exception": {"pid": 228, "cmd": 1, "desc": "Read device errors"},
            "run_hours": {"pid": 104, "cmd": 1, "desc": "Read operating hours"}
        }
    },
    "PSG550": {
        "baudrate": 57600,
        "device_id": 0x02,
        "commands": {
            "pressure": {"pid": 221, "cmd": 1, "desc": "Read pressure (Fixs32en20)"},
            "temperature": {"pid": 222, "cmd": 1, "desc": "Read temperature"},
            "serial_number": {"pid": 207, "cmd": 1, "desc": "Read serial number"},
            "product_name": {"pid": 208, "cmd": 1, "desc": "Read product name"},
            "software_version": {"pid": 218, "cmd": 1, "desc": "Read software version"},
            "device_exception": {"pid": 228, "cmd": 1, "desc": "Read device errors"},
            "run_hours": {"pid": 104, "cmd": 1, "desc": "Read operating hours"},
            "pirani_full_scale": {"pid": 33000, "cmd": 1, "desc": "Read Pirani full scale"},
            "pirani_adjust": {"pid": 417, "cmd": 3, "desc": "Execute Pirani adjustment"}
        }
    },
    "PPG550": {
        "baudrate": 9600,
        "protocol": "ascii",
        "commands": {
            "pressure": {"cmd": "PR3", "type": "read"},
            "temperature": {"cmd": "T", "type": "read"}
        }
    },
    "MAG500": {
        "baudrate": 57600,
        "device_id": 0x14,  # Device ID 20 decimal
        "commands": {
            "pressure": {"pid": 221, "cmd": 1, "desc": "Read pressure (LogFixs32en26)"},
            "temperature": {"pid": 222, "cmd": 1, "desc": "Read temperature"},
            "serial_number": {"pid": 207, "cmd": 1, "desc": "Read serial number"},
            "product_name": {"pid": 208, "cmd": 1, "desc": "Read product name"},
            "software_version": {"pid": 218, "cmd": 1, "desc": "Read software version"},
            "device_exception": {"pid": 228, "cmd": 1, "desc": "Read device errors"},
            "run_hours": {"pid": 104, "cmd": 1, "desc": "Read operating hours"},
            "ccig_status": {"pid": 533, "cmd": 1, "desc": "CCIG Status (0=off, 1=on not ignited, 3=on and ignited)"},
            "ccig_control": {"pid": 529, "cmd": 3, "desc": "Switch CCIG on/off"},
            "ccig_full_scale": {"pid": 503, "cmd": 1, "desc": "Read CCIG full scale"},
            "ccig_safe_state": {"pid": 504, "cmd": 1, "desc": "Read CCIG safe state"}
        }
    },
    "MPG500": {
        "baudrate": 57600,
        "device_id": 0x04,  # Device ID 4 decimal
        "commands": {
            "pressure": {"pid": 221, "cmd": 1, "desc": "Read pressure (LogFixs32en26)"},
            "temperature": {"pid": 222, "cmd": 1, "desc": "Read temperature"},
            "serial_number": {"pid": 207, "cmd": 1, "desc": "Read serial number"},
            "product_name": {"pid": 208, "cmd": 1, "desc": "Read product name"},
            "software_version": {"pid": 218, "cmd": 1, "desc": "Read software version"},
            "device_exception": {"pid": 228, "cmd": 1, "desc": "Read device errors"},
            "run_hours": {"pid": 104, "cmd": 1, "desc": "Read operating hours"},
            "active_sensor": {"pid": 223, "cmd": 1, "desc": "Current active sensor (1=CCIG, 2=Pirani, 3=Mixed)"},
            "pirani_full_scale": {"pid": 33000, "cmd": 1, "desc": "Read Pirani full scale"},
            "pirani_adjust": {"pid": 418, "cmd": 3, "desc": "Execute Pirani adjustment"}
        }
    },
    "CDG045D": {
        "baudrate": 9600,
        "bytesize": serial.EIGHTBITS,
        "parity": serial.PARITY_NONE,
        "stopbits": serial.STOPBITS_ONE,
        "device_id": 0x00,  # Not used for CDG protocol
        "commands": {
            "pressure": {"cmd": "read", "name": "pressure", "desc": "Read pressure"},
            "temperature": {"cmd": "read", "name": "temperature", "desc": "Read temperature status"},
            "software_version": {"cmd": "read", "name": "software_version", "desc": "Read software version"},
            "zero_adjust": {"cmd": "special", "name": "zero_adjust", "desc": "Perform zero adjustment"},
            "reset": {"cmd": "special", "name": "reset", "desc": "Reset gauge"},
            "unit": {"cmd": "read", "name": "unit", "desc": "Read pressure unit"},
        },
        "rs_modes": ["RS232"],  # CDG only supports RS232
        "timeout": 1,  # 1 second timeout
        "write_timeout": 1
    }

}

OUTPUT_FORMATS = ["Hex", "Binary", "ASCII", "UTF-8", "Decimal", "Raw Bytes"]
BAUD_RATES = [9600, 19200, 38400, 57600]


def setup_logging(name: str) -> logging.Logger:
    """Configure logging for the application"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Set to INFO or higher if you want to suppress debug messages

    # Create console handler
    console_handler = logging.StreamHandler()  # StreamHandler logs to console by default
    console_handler.setLevel(logging.DEBUG)  # Match the level you want for the console output

    # Optional: Add a formatter to structure the console output
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Add the console handler to the logger
    logger.addHandler(console_handler)

    return logger