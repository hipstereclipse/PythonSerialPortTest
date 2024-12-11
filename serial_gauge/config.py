import logging
from typing import Dict, Any

import serial

GAUGE_OUTPUT_FORMATS = {
    "CDG025D": "Hex",    # CDG025D uses binary protocol
    "CDG045D": "Hex",    # CDG045D uses binary protocol
    "PSG550": "Hex",     # PSG550 uses binary protocol
    "PCG550": "Hex",     # PCG550 uses binary protocol
    "PPG550": "ASCII",   # PPG550 uses ASCII protocol
    "PPG570": "ASCII",   # PPG570 uses ASCII protocol
    "MAG500": "Hex",     # MAG500 uses binary protocol
    "MPG500": "Hex",     # MPG500 uses binary protocol
    "BPG40x": "Hex",     # BPG40x uses binary protocol
    "BPG552": "Hex",     # BPG552 uses binary protocol
    "BCG450": "Hex",     # BCG450 uses binary protocol
    "BCG552": "Hex",      # BCG552 uses binary protocol
    "TC600": "ASCII"  # TC600 uses ASCII protocol
}

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
        "rs_modes": ["RS232", "RS485"],
        "commands": {
            "pressure": {"cmd": "PR3", "type": "read", "desc": "Read pressure measurement"},
            "temperature": {"cmd": "T", "type": "read", "desc": "Read temperature"},
            "software_version": {"cmd": "FV", "type": "read", "desc": "Read firmware version"},
            "serial_number": {"cmd": "SN", "type": "read", "desc": "Read serial number"},
            "zero_adjust": {"cmd": "VAC", "type": "write", "desc": "Perform zero adjustment"},
            "unit": {"cmd": "U", "type": "read/write", "desc": "Get/set pressure unit"}
        },
        "timeout": 1.0,
        "write_timeout": 1.0
    },

    "PPG570": {
        "baudrate": 9600,
        "protocol": "ascii",
        "rs_modes": ["RS232", "RS485"],
        "commands": {
            "pressure": {"cmd": "PR3", "type": "read", "desc": "Read pressure measurement"},
            "temperature": {"cmd": "T", "type": "read", "desc": "Read temperature"},
            "software_version": {"cmd": "FV", "type": "read", "desc": "Read firmware version"},
            "serial_number": {"cmd": "SN", "type": "read", "desc": "Read serial number"},
            "zero_adjust": {"cmd": "VAC", "type": "write", "desc": "Perform zero adjustment"},
            "unit": {"cmd": "U", "type": "read/write", "desc": "Get/set pressure unit"},
            "atm_pressure": {"cmd": "PR4", "type": "read", "desc": "Read atmospheric pressure"},
            "differential_pressure": {"cmd": "PR5", "type": "read", "desc": "Read differential pressure"},
            "atm_zero": {"cmd": "ATZ", "type": "write", "desc": "Perform atmospheric zero"},
            "atm_adjust": {"cmd": "ATD", "type": "write", "desc": "Perform atmospheric adjustment"}
        },
        "timeout": 1.0,
        "write_timeout": 1.0
    },
    "MAG500": {
        "baudrate": 57600,
        "device_id": 0x14,
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
        "device_id": 0x04,
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
    "CDG025D": {
        "baudrate": 9600,
        "bytesize": serial.EIGHTBITS,
        "parity": serial.PARITY_NONE,
        "stopbits": serial.STOPBITS_ONE,
        "device_id": 0x00,  # Not used for CDG protocol
        "commands": {
            "pressure": {"cmd": "read", "name": "pressure", "desc": "Read pressure"},
            "temperature": {"cmd": "read", "name": "temperature", "desc": "Read temperature status"},
            "software_version": {"cmd": "read", "name": "software_version", "desc": "Read software version"},
            "filter_mode": {"cmd": "read", "name": "filter", "desc": "Read filter mode (0=dynamic, 1=fast, 2=slow)"},
            "output_units": {"cmd": "read", "name": "unit", "desc": "Read pressure units (0=mbar, 1=Torr, 2=Pa)"},
            "zero_adjust": {"cmd": "special", "name": "zero_adjust", "desc": "Perform zero adjustment"},
            "reset": {"cmd": "special", "name": "reset", "desc": "Reset gauge"},
            "factory_reset": {"cmd": "special", "name": "reset_factory", "desc": "Reset to factory defaults"},
            "gauge_type": {"cmd": "read", "name": "cdg_type", "desc": "Read gauge type"},
            "production_number": {"cmd": "read", "name": "production_no", "desc": "Read production number"},
            "calibration_date": {"cmd": "read", "name": "calib_date", "desc": "Read calibration date"},
            "remaining_zero": {"cmd": "read", "name": "remaining_zero", "desc": "Read max remaining zero adjust value"},
            "extended_error": {"cmd": "read", "name": "extended_error", "desc": "Read extended error status"}
        },
        "rs_modes": ["RS232"],  # CDG only supports RS232
        "timeout": 1,  # 1 second timeout
        "write_timeout": 1
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
            "filter_mode": {"cmd": "read", "name": "filter", "desc": "Read filter mode (0=dynamic, 1=fast, 2=slow)"},
            "output_units": {"cmd": "read", "name": "unit", "desc": "Read pressure units (0=mbar, 1=Torr, 2=Pa)"},
            "zero_adjust": {"cmd": "special", "name": "zero_adjust", "desc": "Perform zero adjustment"},
            "reset": {"cmd": "special", "name": "reset", "desc": "Reset gauge"},
            "factory_reset": {"cmd": "special", "name": "reset_factory", "desc": "Reset to factory defaults"},
            "gauge_type": {"cmd": "read", "name": "cdg_type", "desc": "Read gauge type"},
            "production_number": {"cmd": "read", "name": "production_no", "desc": "Read production number"},
            "calibration_date": {"cmd": "read", "name": "calib_date", "desc": "Read calibration date"},
            "remaining_zero": {"cmd": "read", "name": "remaining_zero", "desc": "Read max remaining zero adjust value"},
            "extended_error": {"cmd": "read", "name": "extended_error", "desc": "Read extended error status"},
            "heating_status": {"cmd": "read", "name": "heating_status", "desc": "Read heating status"},
            "temperature_ok": {"cmd": "read", "name": "temperature_ok", "desc": "Check if temperature is OK"},
            "zero_adjust_value": {"cmd": "read", "name": "zero_adjust_value", "desc": "Read zero adjustment value"},
            "dc_output_offset": {"cmd": "read", "name": "dc_output_offset", "desc": "Read DC output offset"}
        },
        "rs_modes": ["RS232"],  # CDG only supports RS232
        "timeout": 1,  # 1 second timeout
        "write_timeout": 1
    },
    "TC600": {
        "baudrate": 9600,
        "bytesize": serial.EIGHTBITS,
        "parity": serial.PARITY_NONE,
        "stopbits": serial.STOPBITS_ONE,
        "device_id": 0x02,  # Default device ID for TC600
        "rs_modes": ["RS232", "RS485"],  # Supports both interfaces
        "commands": {
            "motor_on": {"pid": 23, "cmd": 3, "desc": "Start/stop pump motor"},
            "get_speed": {"pid": 309, "cmd": 1, "desc": "Read actual rotation speed (rpm)"},
            "set_speed": {"pid": 308, "cmd": 3, "desc": "Set nominal rotation speed"},
            "get_current": {"pid": 310, "cmd": 1, "desc": "Read motor current (A)"},
            "get_temp_electronic": {"pid": 326, "cmd": 1, "desc": "Read electronics temperature (°C)"},
            "get_temp_motor": {"pid": 330, "cmd": 1, "desc": "Read motor temperature (°C)"},
            "get_temp_bearing": {"pid": 342, "cmd": 1, "desc": "Read bearing temperature (°C)"},
            "get_error": {"pid": 303, "cmd": 1, "desc": "Read current error code"},
            "get_warning": {"pid": 305, "cmd": 1, "desc": "Read warning status"},
            "operating_hours": {"pid": 311, "cmd": 1, "desc": "Read total operating hours"},
            "set_runup_time": {"pid": 700, "cmd": 3, "desc": "Set maximum run-up time (seconds)"},
            "standby_speed": {"pid": 707, "cmd": 3, "desc": "Set standby rotation speed (%)"},
            "vent_mode": {"pid": 30, "cmd": 3, "desc": "Set venting valve mode"},
            "vent_time": {"pid": 721, "cmd": 3, "desc": "Set venting time (seconds)"}
        },
        "timeout": 1.0,
        "write_timeout": 1.0
    }
}

OUTPUT_FORMATS = ["Hex", "Binary", "ASCII", "UTF-8", "Decimal", "Raw Bytes"]
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]

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