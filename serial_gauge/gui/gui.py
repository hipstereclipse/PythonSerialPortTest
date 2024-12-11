"""
Consolidated GUI module for vacuum gauge communication interface.
Combines widget definitions and main application logic into a single file.
Supports RS232/RS485 communication with various gauge types.
"""

import queue
import sys
import threading
import tkinter as tk
from io import StringIO
from tkinter import ttk
from datetime import datetime
import time
import logging
import serial
import serial.tools.list_ports
from typing import Optional, Dict, Any, Callable

# Update imports to use correct package paths
from ..config import GAUGE_PARAMETERS, OUTPUT_FORMATS, GAUGE_OUTPUT_FORMATS
from ..communicator import IntelligentCommandSender, ResponseHandler, GaugeCommunicator, GaugeTester
from ..models import GaugeCommand, GaugeResponse
from ..protocols import *

# ================================
# Command Frame: Handles Gauge Commands
# ================================
class CommandFrame(ttk.LabelFrame):
    """Frame for handling gauge commands - both quick commands and detailed command construction"""

    def __init__(self, parent, gauge_var: tk.StringVar, command_callback: Callable):
        """Initialize command frame with gauge selection and callback"""
        super().__init__(parent, text="Commands")

        # Store references to parent variables and callback
        self.gauge_var = gauge_var
        self.command_callback = command_callback
        self.communicator = None  # Will be set by main application

        # Initialize internal state variables
        self.cmd_var = tk.StringVar()  # Current selected command
        self.cmd_type = tk.StringVar(value="?")  # Query/Set mode
        self.param_var = tk.StringVar()  # Command parameters
        self.desc_var = tk.StringVar()  # Command description

        # Create GUI elements
        self._create_widgets()

        # Set up variable traces
        self.gauge_var.trace('w', self._update_commands)
        self.cmd_var.trace('w', self._update_command_info)
        self.cmd_type.trace('w', self._update_parameter_state)

    def _create_widgets(self):
        # Manual Command Section
        manual_frame = ttk.LabelFrame(self, text="Manual Command")
        manual_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(manual_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.manual_cmd_entry = ttk.Entry(manual_frame, width=50)
        self.manual_cmd_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.manual_send_button = ttk.Button(
            manual_frame,
            text="Send",
            command=self.send_manual_command
        )
        self.manual_send_button.pack(side=tk.LEFT, padx=5)

        # Quick Commands Section
        quick_frame = ttk.LabelFrame(self, text="Quick Commands")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        # Command selection
        ttk.Label(quick_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.cmd_combo = ttk.Combobox(
            quick_frame,
            textvariable=self.cmd_var,
            state="readonly",
            width=30
        )
        self.cmd_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Command type radio buttons
        radio_frame = ttk.Frame(quick_frame)
        radio_frame.pack(side=tk.LEFT, padx=5)

        self.query_radio = ttk.Radiobutton(
            radio_frame,
            text="Query (?)",
            variable=self.cmd_type,
            value="?"
        )
        self.set_radio = ttk.Radiobutton(
            radio_frame,
            text="Set (!)",
            variable=self.cmd_type,
            value="!"
        )
        self.query_radio.pack(side=tk.LEFT, padx=5)
        self.set_radio.pack(side=tk.LEFT, padx=5)

        # Parameter frame
        param_frame = ttk.Frame(self)  # Changed to be direct child of self for better layout
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        self.param_label = ttk.Label(param_frame, text="Parameter:")
        self.param_label.pack(side=tk.LEFT, padx=5)

        # Create both Entry and Combobox for parameters
        self.param_entry = ttk.Entry(
            param_frame,
            textvariable=self.param_var,
            width=30
        )

        self.param_combo = ttk.Combobox(
            param_frame,
            textvariable=self.param_var,
            state="readonly",
            width=30
        )

        # Initially pack neither - they will be shown as needed
        # self.param_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.quick_send_button = ttk.Button(
            param_frame,
            text="Send",
            command=self.send_quick_command
        )
        self.quick_send_button.pack(side=tk.RIGHT, padx=5)

        # Description label
        self.desc_label = ttk.Label(
            self,
            textvariable=self.desc_var,
            wraplength=500
        )
        self.desc_label.pack(fill=tk.X, padx=5, pady=5)

    def _update_parameter_widget(self, cmd_info: dict):
        """Update parameter input widget based on command type"""
        # Remove both widgets first
        self.param_entry.pack_forget()
        self.param_combo.pack_forget()

        if self.cmd_type.get() == "!":
            if "options" in cmd_info:
                # Use Combobox for predefined options
                options = [f"{val} - {desc}" for val, desc in zip(cmd_info["options"], cmd_info["option_desc"])]
                self.param_combo['values'] = options
                self.param_combo.set(options[0] if options else "")
                self.param_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            else:
                # Use Entry for numeric values
                self.param_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                if "min" in cmd_info and "max" in cmd_info:
                    self.desc_var.set(
                        f"{cmd_info['desc']} (Range: {cmd_info['min']}-{cmd_info['max']} {cmd_info.get('unit', '')})")

    def _update_commands(self, *args):
        """Update available commands when gauge type changes"""
        gauge_type = self.gauge_var.get()
        if gauge_type in GAUGE_PARAMETERS:
            # Get commands from gauge parameters
            commands = GAUGE_PARAMETERS[gauge_type].get("commands", {})
            # Create list of command names with descriptions
            cmd_list = [f"{name} - {cmd_info['desc']}"
                        for name, cmd_info in commands.items()]
            self.cmd_combo['values'] = cmd_list
            if cmd_list:
                self.cmd_combo.set(cmd_list[0])
                # Update command info for the first command
                self._update_command_info()

    def _update_command_info(self, *args):
        """Update command information and UI state when selected command changes"""
        selected = self.cmd_var.get()
        if selected and self.communicator:
            cmd_name = selected.split(" - ")[0]
            cmd_info = self.communicator.protocol._command_defs.get(cmd_name, {})

            # Update description
            self.desc_var.set(cmd_info.get("desc", "No description available"))

            # Configure radio buttons based on command type
            if cmd_info.get("write", False):
                self.query_radio.configure(state="normal")
                self.set_radio.configure(state="normal")
            else:
                self.cmd_type.set("?")
                self.query_radio.configure(state="normal")
                self.set_radio.configure(state="disabled")

            # Update parameter state
            self._update_parameter_state()

    def send_manual_command(self):
        """Send manual command entered by user"""
        if not self.communicator:
            return

        cmd = self.manual_cmd_entry.get().strip()
        if cmd:
            result = IntelligentCommandSender.send_manual_command(
                self.communicator,
                cmd
            )

            self.manual_cmd_entry.delete(0, tk.END)

            if self.command_callback:
                response = GaugeResponse(
                    raw_data=bytes.fromhex(result.get('response_raw', '')) if result.get('response_raw') else b'',
                    formatted_data=result.get('response_formatted', ''),
                    success=result.get('success', False),
                    error_message=result.get('error', None)
                )
                self.command_callback(cmd, response=response)

    def _update_parameter_state(self, *args):
        """Update parameter widget state based on command type and available options"""
        if not self.communicator or not self.cmd_var.get():
            return

        cmd_name = self.cmd_var.get().split(" - ")[0]
        cmd_info = self.communicator.protocol._command_defs.get(cmd_name, {})

        # Hide both widgets initially
        self.param_entry.pack_forget()
        self.param_combo.pack_forget()

        if self.cmd_type.get() == "!":
            self.param_label.configure(state="normal")

            if "options" in cmd_info:
                # Show dropdown for predefined options
                options = [f"{val} - {desc}" for val, desc in
                           zip(cmd_info["options"], cmd_info["option_desc"])]
                self.param_combo['values'] = options
                self.param_combo.set(options[0] if options else "")
                self.param_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                self.param_combo.configure(state="readonly")
            else:
                # Show entry field for numeric values
                self.param_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                self.param_entry.configure(state="normal")
                # Add range hint to description if available
                if "min" in cmd_info and "max" in cmd_info:
                    self.desc_var.set(
                        f"{cmd_info['desc']} (Range: {cmd_info['min']}-{cmd_info['max']} {cmd_info.get('unit', '')})")
        else:
            self.param_label.configure(state="disabled")
            self.param_var.set("")  # Clear parameter value

    def send_quick_command(self):
        """Send quick command based on selection"""
        if not self.communicator:
            return

        selected = self.cmd_var.get()
        if selected:
            cmd_name = selected.split(" - ")[0]

            # Extract the actual value from the parameter if it's an option with description
            param_value = self.param_var.get()
            if " - " in param_value:
                param_value = param_value.split(" - ")[0]

            command = GaugeCommand(
                name=cmd_name,
                command_type=self.cmd_type.get(),
                parameters={"value": param_value} if self.cmd_type.get() == "!" else None
            )

            response = self.communicator.send_command(command)

            if self.command_callback:
                self.command_callback(cmd_name, response=response)

    def set_enabled(self, enabled: bool):
        """Enable or disable all interactive widgets in the frame"""
        state = "normal" if enabled else "disabled"

        # Update all widget states
        widgets = [
            self.manual_cmd_entry,
            self.manual_send_button,
            self.cmd_combo,
            self.query_radio,
            self.set_radio,
            self.param_entry,
            self.quick_send_button
        ]

        for widget in widgets:
            widget.configure(state=state)

        # If enabled, recheck the command state to properly set radio buttons
        if enabled:
            self._update_command_info()


# ================================
# Serial Settings Frame: Manages RS232/RS485 Settings
# ================================
class SerialSettingsFrame(ttk.LabelFrame):
    """
    Frame for controlling RS232/RS485 serial port settings and manual command entry.
    Provides UI elements to configure serial parameters and send arbitrary commands.
    """

    def __init__(self, parent, settings_callback: Callable, command_callback: Callable):
        """
        Initialize the SerialSettingsFrame with callbacks for settings changes and commands.

        Args:
            parent: The parent Tkinter widget.
            settings_callback (Callable): Function to call when settings are applied.
            command_callback (Callable): Function to call when a manual command is sent.
        """
        super().__init__(parent, text="Serial Settings & Manual Command")

        # Store callbacks for settings changes and command sending
        self.settings_callback = settings_callback
        self.command_callback = command_callback
        self.logger = None  # Will be set by main application

        # Initialize serial settings variables with default values
        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")
        self.rs485_mode = tk.BooleanVar(value=False)
        self.rs485_addr = tk.StringVar(value="254")

        # Initialize command history for manual command entry
        self.cmd_history = []
        self.history_index = -1

        # Create and layout all widgets within the frame
        self._create_widgets()

    def set_logger(self, logger):
        """Set the logger instance to use for messages"""
        self.logger = logger

    def _create_widgets(self):
        """
        Create and layout all widgets in the serial settings frame.
        This includes serial configuration options and manual command entry.
        """
        # ============================
        # Serial Settings Section
        # ============================
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # ----------------------------
        # Left Side: Basic Serial Settings
        # ----------------------------
        left_frame = ttk.Frame(settings_frame)
        left_frame.pack(side=tk.LEFT, padx=5)

        # Baud Rate Selection
        ttk.Label(left_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_menu = ttk.Combobox(
            left_frame,
            textvariable=self.baud_var,
            values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
            width=7
        )
        baud_menu.pack(side=tk.LEFT, padx=2)

        # Byte Size Selection
        ttk.Label(left_frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bytesize_menu = ttk.Combobox(
            left_frame,
            textvariable=self.bytesize_var,
            values=["5", "6", "7", "8"],
            width=2
        )
        bytesize_menu.pack(side=tk.LEFT, padx=2)

        # ----------------------------
        # Center: Parity and Stop Bits
        # ----------------------------
        center_frame = ttk.Frame(settings_frame)
        center_frame.pack(side=tk.LEFT, padx=5)

        # Parity Selection
        ttk.Label(center_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_menu = ttk.Combobox(
            center_frame,
            textvariable=self.parity_var,
            values=["N", "E", "O", "M", "S"],
            width=2
        )
        parity_menu.pack(side=tk.LEFT, padx=2)

        # Stop Bits Selection
        ttk.Label(center_frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stopbits_menu = ttk.Combobox(
            center_frame,
            textvariable=self.stopbits_var,
            values=["1", "1.5", "2"],
            width=3
        )
        stopbits_menu.pack(side=tk.LEFT, padx=2)

        # ----------------------------
        # Right Side: RS485 Settings
        # ----------------------------
        right_frame = ttk.Frame(settings_frame)
        right_frame.pack(side=tk.LEFT, padx=5)

        rs485_frame = ttk.Frame(right_frame)
        rs485_frame.pack(side=tk.LEFT, padx=2)

        # RS485 Mode Checkbox
        self.rs485_check = ttk.Checkbutton(
            rs485_frame,
            text="RS485",
            variable=self.rs485_mode,
            command=self._on_rs485_change
        )
        self.rs485_check.pack(side=tk.LEFT, padx=2)

        # RS485 Address Entry
        ttk.Label(rs485_frame, text="Addr:").pack(side=tk.LEFT, padx=2)
        self.rs485_addr_entry = ttk.Entry(
            rs485_frame,
            textvariable=self.rs485_addr,
            width=4
        )
        self.rs485_addr_entry.pack(side=tk.LEFT, padx=2)

        # Apply Settings Button
        ttk.Button(
            right_frame,
            text="Apply",
            command=self.apply_settings,
            width=8
        ).pack(side=tk.LEFT, padx=5)

        # Initialize RS485 address entry state based on RS485 mode
        self._update_rs485_address_state()


    def _update_rs485_address_state(self):
        """
        Update the state (enabled/disabled) of the RS485 address entry field
        based on whether RS485 mode is enabled.
        """
        state = 'normal' if self.rs485_mode.get() else 'disabled'
        self.rs485_addr_entry.configure(state=state)

    def _on_rs485_change(self):
        """
        Handle changes to the RS485 mode selection.
        Updates the RS485 address entry state and applies the new settings.
        """
        self._update_rs485_address_state()
        settings = self.get_current_settings()
        self.settings_callback(settings)

    def get_current_settings(self) -> dict:
        """
        Retrieve the current serial settings, including RS485 configuration.

        Returns:
            dict: A dictionary containing all current serial settings.
        """
        return {
            'baudrate': int(self.baud_var.get()),
            'bytesize': int(self.bytesize_var.get()),
            'parity': self.parity_var.get(),
            'stopbits': float(self.stopbits_var.get()),
            'rs485_mode': self.rs485_mode.get(),
            'rs485_address': int(self.rs485_addr.get())
        }

    def apply_settings(self):
        """
        Apply all serial settings by invoking the settings callback.
        This sends the current settings to the main application for application.
        """
        settings = self.get_current_settings()
        self.settings_callback(settings)

        # Create settings summary message
        settings_msg = f"\nSerial settings applied:\n"
        settings_msg += f"Baud Rate: {settings['baudrate']}\n"
        settings_msg += f"Data Bits: {settings['bytesize']}\n"
        settings_msg += f"Parity: {settings['parity']}\n"
        settings_msg += f"Stop Bits: {settings['stopbits']}\n"
        if settings['rs485_mode']:
            settings_msg += f"RS485 Mode: Enabled\n"
            settings_msg += f"RS485 Address: {settings['rs485_address']}\n"
        else:
            settings_msg += f"RS485 Mode: Disabled\n"

        # Log the settings message if logger is available
        if self.logger:
            self.logger.info(settings_msg)

    def send_command(self, event=None):
        """
        Send a manual command entered by the user, with support for command history.

        Args:
            event: The event that triggered this function (optional).

        Returns:
            str: 'break' to prevent default handling of the event.
        """
        cmd = self.cmd_entry.get().strip()
        if cmd:
            # Add to history if not a duplicate of the last command
            if not self.cmd_history or cmd != self.cmd_history[-1]:
                self.cmd_history.append(cmd)
            self.history_index = len(self.cmd_history)

            # Send command through callback
            self.command_callback(cmd)

            # Clear the entry field after sending
            self.cmd_entry.delete(0, tk.END)
        return 'break'  # Prevent default handling

    def history_up(self, event):
        """
        Navigate upward through the command history when the Up arrow key is pressed.

        Args:
            event: The event that triggered this function.

        Returns:
            str: 'break' to prevent default handling of the event.
        """
        if self.cmd_history and self.history_index > 0:
            self.history_index -= 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        return 'break'

    def history_down(self, event):
        """
        Navigate downward through the command history when the Down arrow key is pressed.

        Args:
            event: The event that triggered this function.

        Returns:
            str: 'break' to prevent default handling of the event.
        """
        if self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        else:
            self.history_index = len(self.cmd_history)
            self.cmd_entry.delete(0, tk.END)
        return 'break'

    def set_rs485_mode(self, enabled: bool, address: int = 254):
        """
        Enable or disable RS485 mode with an optional address.

        Args:
            enabled (bool): True to enable RS485 mode, False to disable.
            address (int, optional): The RS485 address to set. Defaults to 254.
        """
        self.rs485_mode.set(enabled)
        self.rs485_addr.set(str(address))
        self._update_rs485_address_state()
        self._on_rs485_change()


# ================================
# Debug Frame: Provides Debugging Tools
# ================================
class DebugFrame(ttk.LabelFrame):
    """
    Frame for debugging options and testing gauge communication.
    Uses the same output format as the main interface for consistency.
    """

    def __init__(self, parent, baud_callback: Callable, enq_callback: Callable, settings_callback: Callable,
                 output_format: tk.StringVar):
        """
        Initialize the debug frame with callbacks and shared output format.

        Args:
            parent: Parent widget
            baud_callback: Function to test different baud rates
            enq_callback: Function to send ENQ test
            settings_callback: Function to show current settings
            output_format: Shared StringVar containing selected output format
        """
        super().__init__(parent, text="Debug")

        # Store reference to shared output format
        self.output_format = output_format

        # Store reference to parent for accessing OutputFrame
        self.parent = parent

        # Create main controls frame
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Add baud rate testing button
        self.baud_button = ttk.Button(
            controls_frame,
            text="Try All Baud Rates",
            command=lambda: self._wrap_debug_callback(baud_callback)
        )
        self.baud_button.pack(side=tk.LEFT, padx=5)

        # Add ENQ testing button
        self.enq_button = ttk.Button(
            controls_frame,
            text="Send ENQ",
            command=lambda: self._wrap_debug_callback(enq_callback)
        )
        self.enq_button.pack(side=tk.LEFT, padx=5)

        # Add settings display button
        self.settings_button = ttk.Button(
            controls_frame,
            text="Show Settings",
            command=settings_callback
        )
        self.settings_button.pack(side=tk.LEFT, padx=5)

        # Track buttons that don't require connection
        self.non_connection_buttons = [self.settings_button]

    def _wrap_debug_callback(self, callback: Callable) -> Any:
        """
        Wrap debug callbacks to capture and format their output.

        Args:
            callback: The original callback function

        Returns:
            The result of the callback function
        """
        try:
            # Execute callback
            result = callback()

            # Get the most recent debug messages
            if hasattr(self.parent, 'output_frame'):
                debug_text = self.parent.output_frame.output_text.get("1.0", tk.END)
                # Format any new protocol messages
                formatted = self._format_debug_messages(debug_text)
                # Update the output
                if formatted != debug_text:
                    self.parent.output_frame.clear()
                    self.parent.output_frame.append_log(formatted)

            return result

        except Exception as e:
            if hasattr(self.parent, 'output_frame'):
                self.parent.output_frame.append_log(f"Debug error: {str(e)}")
            return None

    def _format_debug_messages(self, text: str) -> str:
        """
        Format all debug messages according to current output format.

        Args:
            text: The text containing debug messages

        Returns:
            Formatted debug text
        """
        lines = []
        for line in text.split('\n'):
            if "command:" in line.lower() or "response:" in line.lower():
                formatted = self._format_protocol_message(line)
                lines.append(formatted)
            else:
                lines.append(line)
        return '\n'.join(lines)

    def _format_protocol_message(self, message: str) -> str:
        """
        Format a protocol message according to current output format.

        Args:
            message: The protocol message to format

        Returns:
            Formatted message
        """
        try:
            # Split into prefix and data parts
            prefix, data = message.split(':', 1)
            data = data.strip()

            # Convert data to bytes if needed
            if data.startswith("b'") or data.startswith('b"'):
                data_bytes = eval(data)
            elif all(c in '0123456789ABCDEFabcdef ' for c in data):
                data_bytes = bytes.fromhex(data.replace(' ', ''))
            else:
                return message

            # Format according to selected output format
            current_format = self.output_format.get()

            if current_format == "Hex":
                formatted_data = ' '.join(f'{b:02X}' for b in data_bytes)
            elif current_format == "ASCII":
                formatted_data = data_bytes.decode('ascii', errors='replace')
            elif current_format == "Decimal":
                formatted_data = ' '.join(str(b) for b in data_bytes)
            elif current_format == "Binary":
                formatted_data = ' '.join(f'{b:08b}' for b in data_bytes)
            elif current_format == "UTF-8":
                formatted_data = data_bytes.decode('utf-8', errors='replace')
            else:  # Raw Bytes
                formatted_data = str(data_bytes)

            # For ASCII and UTF-8, add protocol interpretation
            if current_format in ["ASCII", "UTF-8"] and len(formatted_data) >= 10:
                addr = formatted_data[0:3]
                cmd_type = "Write" if formatted_data[3:5] == "10" else "Read"
                param = formatted_data[5:8]
                data_section = formatted_data[8:] if len(formatted_data) > 8 else ""

                formatted_data = f"Addr={addr} {cmd_type} Param={param} Data={data_section}"

            return f"{prefix}: {formatted_data}"

        except Exception as e:
            # If formatting fails, return original message
            return message

    def set_enabled(self, enabled: bool):
        """
        Enable or disable debug buttons based on connection state.

        Args:
            enabled: True to enable buttons, False to disable
        """
        state = "normal" if enabled else "disabled"
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                if child not in self.non_connection_buttons:
                    child.config(state=state)

# ================================
# Output Frame: Displays Logs and Responses
# ================================
class OutputFrame(ttk.LabelFrame):
    """
    Frame for displaying command outputs and response logs.
    Provides a text area for logs and an option to select output formats.
    """

    def __init__(self, parent, output_format: tk.StringVar):
        """
        Initialize the OutputFrame with format selection.

        Args:
            parent: The parent Tkinter widget.
            output_format (tk.StringVar): Variable holding the selected output format.
        """
        super().__init__(parent, text="Output")
        self.output_format = output_format

        # Create and layout output format selection controls
        format_frame = ttk.Frame(self)
        format_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(format_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            format_frame,
            self.output_format,
            "ASCII",
            *OUTPUT_FORMATS
        ).pack(side=tk.LEFT, padx=5)

        # Create and layout the output text area
        self.output_text = tk.Text(self, height=20, width=80, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add a scrollbar to the output text area
        scrollbar = ttk.Scrollbar(self.output_text, orient="vertical", command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

    def append_log(self, message: str):
        """
        Add a timestamped message to the log.

        Args:
            message (str): The message to append to the log.
        """
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)  # Scroll to the end

    def clear(self):
        """
        Clear all text from the output log.
        """
        self.output_text.delete(1.0, tk.END)


# ================================
# Main Application Class
# ================================
class GaugeApplication:
    """
    Main application class for the vacuum gauge communication interface.
    Manages the overall GUI, serial communication, and user interactions.
    """

    def __init__(self, root: tk.Tk):
        """Initialize the main application window and all components."""
        # Initialize main window properties
        self.root = root
        self.root.title("Vacuum Gauge Communication Interface")
        self.root.geometry("800x650")

        # Initialize variables for port, gauge type, and output format
        self.selected_port = tk.StringVar()
        self.selected_gauge = tk.StringVar(value="PPG550")
        self.output_format = tk.StringVar(value="ASCII")

        # Initialize continuous reading variables
        self.continuous_var = tk.BooleanVar(value=False)
        self.continuous_thread = None
        self.response_queue = queue.Queue()
        self.update_interval = tk.StringVar(value="1000")

        # Initialize default serial settings
        self.current_serial_settings = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        # Initialize the communicator object as None (no connection)
        self.communicator: Optional[GaugeCommunicator] = None

        # Create and layout all GUI elements
        self._create_gui()

        # Set up variable traces
        self.output_format.trace('w', self._on_output_format_change)
        self.selected_gauge.trace('w', self._on_gauge_change)

        # Initial refresh to populate available COM ports
        self.refresh_ports()

    def _create_gui(self):
        """Create and layout all GUI elements."""
        # Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Port Selection Controls
        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        # Button to refresh the list of available COM ports
        ttk.Button(
            conn_frame,
            text="Refresh",
            command=self.refresh_ports
        ).pack(side=tk.LEFT, padx=5)

        # Gauge Selection Controls
        ttk.Label(conn_frame, text="Gauge:").pack(side=tk.LEFT, padx=5)
        self.gauge_menu = ttk.OptionMenu(
            conn_frame,
            self.selected_gauge,
            "PCG550",
            *GAUGE_PARAMETERS.keys()
        )
        self.gauge_menu.pack(side=tk.LEFT, padx=5)

        # Connect/Disconnect Button
        self.connect_button = ttk.Button(
            conn_frame,
            text="Connect",
            command=self.connect_disconnect
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # Serial Settings Frame
        self.serial_frame = SerialSettingsFrame(
            self.root,
            self.apply_serial_settings,
            self.send_manual_command
        )
        self.serial_frame.set_logger(self)  # Pass self as logger since GaugeApplication implements logger interface
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        # Command Frame
        self.cmd_frame = CommandFrame(
            parent=self.root,
            gauge_var=self.selected_gauge,
            command_callback=self.send_command
        )
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Debug Frame
        self.debug_frame = DebugFrame(
            self.root,
            self.try_all_baud_rates,
            self.send_enq,
            self.show_port_settings,
            self.output_format  # Pass output format variable
        )
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        # Output Frame
        self.output_frame = OutputFrame(
            self.root,
            self.output_format
        )
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create (but don't pack) Continuous Reading Frame
        self.continuous_frame = ttk.LabelFrame(self.root, text="Continuous Reading")

        # Continuous Reading Controls
        ttk.Checkbutton(
            self.continuous_frame,
            text="View Continuous Reading",
            variable=self.continuous_var,
            command=self.toggle_continuous_reading
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(self.continuous_frame, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(
            self.continuous_frame,
            textvariable=self.update_interval,
            width=6
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            self.continuous_frame,
            text="Update",
            command=self._update_interval_value
        ).pack(side=tk.LEFT, padx=5)

        # Start GUI update loop
        self.update_gui()

    def update_gui(self):
        """Update GUI with queued responses."""
        while not self.response_queue.empty():
            try:
                response = self.response_queue.get_nowait()
                if response.success:
                    self.output_frame.append_log(f"\n{response.formatted_data}")
                else:
                    self.output_frame.append_log(f"\nError: {response.error_message}")
            except queue.Empty:
                pass
        self.root.after(50, self.update_gui)

    def _on_gauge_change(self, *args):
        """Handle changes to the gauge type selection."""
        gauge_type = self.selected_gauge.get()

        if gauge_type in GAUGE_PARAMETERS:
            # Retrieve default settings for the selected gauge
            params = GAUGE_PARAMETERS[gauge_type]

            # Update serial settings in the UI based on gauge defaults
            self.serial_frame.baud_var.set(str(params["baudrate"]))

            # Determine RS485 mode and address based on gauge type
            rs485_supported = "rs_modes" in params and "RS485" in params["rs_modes"]
            rs485_address = params.get("address", 254) if rs485_supported else 254

            # Update RS485 mode in the UI
            self.serial_frame.set_rs485_mode(rs485_supported, rs485_address)

            # Set the default output format for the selected gauge type
            self.output_format.set(GAUGE_OUTPUT_FORMATS.get(gauge_type))

            # Hide continuous frame when changing gauge type if not connected
            if not self.communicator:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

            # Apply new serial settings
            self.apply_serial_settings({
                'baudrate': params["baudrate"],
                'bytesize': params.get("bytesize", 8),
                'parity': params.get("parity", 'N'),
                'stopbits': params.get("stopbits", 1.0),
                'rs485_mode': rs485_supported,
                'rs485_address': rs485_address
            })

    def toggle_continuous_reading(self):
        """Handle continuous reading toggle."""
        if not self.communicator:
            self.continuous_var.set(False)
            return

        if self.continuous_var.get():
            self.start_continuous_reading()
        else:
            self.stop_continuous_reading()

    def start_continuous_reading(self):
        """Start continuous reading thread."""
        if self.continuous_thread and self.continuous_thread.is_alive():
            return

        self.communicator.set_continuous_reading(True)
        self.continuous_thread = threading.Thread(
            target=self.continuous_reading_thread,
            daemon=True
        )
        self.continuous_thread.start()

    def stop_continuous_reading(self):
        """Stop continuous reading thread."""
        if self.communicator:
            self.communicator.stop_continuous_reading()
        if self.continuous_thread:
            self.continuous_thread.join(timeout=1.0)
            self.continuous_thread = None

    def continuous_reading_thread(self):
        """Thread function for continuous reading."""
        try:
            interval = int(self.update_interval.get()) / 1000.0
            self.communicator.read_continuous(
                lambda response: self.response_queue.put(response),
                interval
            )
        except Exception as e:
            self.response_queue.put(GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=f"Thread error: {str(e)}"
            ))

    def _update_interval_value(self):
        """Update continuous reading interval."""
        try:
            interval = int(self.update_interval.get())
            self.log_message(f"Update interval set to: {interval} ms")
            if self.continuous_var.get():
                self.stop_continuous_reading()
                self.start_continuous_reading()
        except ValueError:
            self.log_message("Invalid interval value. Please enter a valid integer.")

    def refresh_ports(self):
        """
        Refresh the list of available COM ports and update the port selection menu.
        """
        ports = [port.device for port in serial.tools.list_ports.comports()]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(
                label=port,
                command=lambda p=port: self.selected_port.set(p)
            )
        if ports:
            self.selected_port.set(ports[0])  # Select the first available port by default
        else:
            self.selected_port.set("")  # Clear selection if no ports are available

    def connect_disconnect(self):
        """Handle connection/disconnection logic."""
        if self.communicator is None:  # Connect
            try:
                # Create new communicator instance
                self.communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )

                # Configure and connect
                if self.communicator.connect():
                    self.connect_button.config(text="Disconnect")
                    self.log_message("Connection established.")
                    self.cmd_frame.communicator = self.communicator
                    self.cmd_frame.set_enabled(True)
                    self.debug_frame.set_enabled(True)
                    # Update continuous frame visibility based on gauge type
                    self.update_continuous_visibility()
                else:
                    self.log_message("Failed to connect.")
                    self.communicator = None
            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.communicator = None
        else:  # Disconnect
            try:
                self.stop_continuous_reading()
                self.communicator.disconnect()
                self.communicator = None
                self.connect_button.config(text="Connect")
                self.log_message("Disconnected.")
                self.cmd_frame.set_enabled(False)
                self.debug_frame.set_enabled(False)
                self.continuous_var.set(False)
                # Hide continuous frame on disconnect
                self.continuous_frame.pack_forget()
            except Exception as e:
                self.log_message(f"Disconnection error: {e}")
    def _on_output_format_change(self, *args):
        """
        Handle changes to the output format selection.
        Updates the communicator's output format and logs the change.
        """
        new_format = self.output_format.get()
        if self.communicator:
            self.communicator.set_output_format(new_format)
        self.log_message(f"Output format changed to: {new_format}")

    def apply_serial_settings(self, settings: dict):
        """
        Apply new serial port settings by updating the current settings
        and configuring the communicator if connected.

        Args:
            settings (dict): Dictionary containing the new serial settings.
        """
        try:
            # Update the current serial settings with the new values
            self.current_serial_settings.update(settings)

            if self.communicator:
                # Apply settings to the active communicator's serial port
                if self.communicator.ser and self.communicator.ser.is_open:
                    self.communicator.ser.baudrate = settings['baudrate']
                    self.communicator.ser.bytesize = settings['bytesize']
                    self.communicator.ser.parity = settings['parity']
                    self.communicator.ser.stopbits = settings['stopbits']

                    # Handle RS485 mode settings
                    if settings.get('rs485_mode', False):
                        self.communicator.set_rs_mode("RS485")
                        if isinstance(self.communicator.protocol, PPGProtocol):  # Changed from PPG550Protocol
                            self.communicator.protocol.address = settings.get('rs485_address', 254)
                    else:
                        self.communicator.set_rs_mode("RS232")

                    self.log_message(f"Serial settings updated: {settings}")
                    if settings.get('rs485_mode', False):
                        self.log_message(f"RS485 Address: {settings.get('rs485_address', 254)}")

        except Exception as e:
            self.log_message(f"Failed to update serial settings: {str(e)}")

    def send_command(self, command: str, response: Optional[GaugeResponse] = None):
        """
        Handle command execution and display results.

        Args:
            command (str): The command that was sent
            response (Optional[GaugeResponse]): The response from the gauge
        """
        if response:
            if response.success:
                self.log_message(f">: {command}")
                self.log_message(f"<: {response.formatted_data}")
            else:
                self.log_message(f"Command failed: {response.error_message}")
        else:
            self.log_message(f"\nUnable to send command: {command}")

    def send_manual_command(self, command: str):
        """
        Handle sending a manual command through the CommandFrame.

        Args:
            command (str): The manual command string to be sent.
        """
        if not hasattr(self, 'cmd_frame') or not self.cmd_frame:
            self.log_message("CommandFrame is not available.")
            return

        # Pass the manual command to the CommandFrame's process method
        self.cmd_frame.process_command(command)

    def try_all_baud_rates(self):
        """
        Test connection with different baud rates to establish communication with the gauge.
        Uses GaugeTester to systematically test different baud rates and identify the gauge.
        """
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None

        self.log_message("\n=== Testing Baud Rates ===")
        port = self.selected_port.get()

        try:
            # Create temporary communicator for testing
            temp_communicator = GaugeCommunicator(
                port=port,
                gauge_type=self.selected_gauge.get(),
                logger=self
            )

            # Set the output format according to current selection
            temp_communicator.set_output_format(self.output_format.get())

            # Create tester instance
            tester = GaugeTester(temp_communicator, self)

            # Run the baud rate test
            success = tester.try_all_baud_rates(port)

            if success:
                successful_baud = temp_communicator.baudrate
                self.serial_frame.baud_var.set(str(successful_baud))
                self.apply_serial_settings({
                    'baudrate': successful_baud,
                    'bytesize': 8,
                    'parity': 'N',
                    'stopbits': 1.0
                })

                # Test the connection using the tester's test commands
                test_results = tester.run_all_tests()
                for cmd_name, result in test_results.get("commands_tested", {}).items():
                    if result.get("success"):
                        self.log_message(f"Test {cmd_name}: {result.get('response', 'OK')}")
                    else:
                        self.log_message(f"Test {cmd_name} failed: {result.get('error', 'Unknown error')}")

                temp_communicator.disconnect()
                return True
            else:
                if temp_communicator and temp_communicator.ser and temp_communicator.ser.is_open:
                    temp_communicator.disconnect()
                return False

        except Exception as e:
            self.log_message(f"Baud rate testing error: {str(e)}")
            import traceback
            self.log_message(f"Traceback: {traceback.format_exc()}")
            if temp_communicator and temp_communicator.ser and temp_communicator.ser.is_open:
                temp_communicator.disconnect()
            return False

    def update_continuous_visibility(self):
        """Update visibility of continuous reading controls."""
        if hasattr(self, 'continuous_frame'):
            if self.communicator and self.communicator.continuous_output:
                # Pack the continuous frame after the output frame
                self.continuous_frame.pack(fill="x", padx=5, pady=5)  # Pack at the bottom
            else:
                # Hide the continuous frame and reset the checkbox
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

    def send_enq(self):
        """
        Send an ENQ (Enquiry) character to test communication with the gauge.
        Uses GaugeTester to handle the ENQ test and logs the response.
        """
        if not self.communicator or not self.communicator.ser or not self.communicator.ser.is_open:
            self.log_message("Not connected")
            return

        try:
            # Set output format before sending ENQ
            self.communicator.set_output_format(self.output_format.get())

            # Create tester instance and perform ENQ test
            tester = GaugeTester(self.communicator, self)
            if tester.send_enq():
                self.log_message("> ENQ test successful")
            else:
                self.log_message("> ENQ test failed")
        except Exception as e:
            self.log_message(f"ENQ test error: {str(e)}")

    def show_port_settings(self):
        """
        Display the current serial port settings in the output log.
        If connected, shows active port settings; otherwise, shows saved settings.
        """
        try:
            if self.communicator and self.communicator.ser:
                # Display active serial port settings
                ser = self.communicator.ser
                settings = f"""
=== Port Settings ===
Port: {ser.port}
Baudrate: {ser.baudrate}
Bytesize: {ser.bytesize}
Parity: {ser.parity}
Stopbits: {ser.stopbits}
Timeout: {ser.timeout}
XonXoff: {ser.xonxoff}
RtsCts: {ser.rtscts}
DsrDtr: {ser.dsrdtr}
"""
                self.log_message(settings)
            else:
                # Display saved serial settings for the next connection
                self.log_message("Not connected - showing saved settings:")
                settings = f"""
=== Saved Settings ===
Baudrate: {self.current_serial_settings['baudrate']}
Bytesize: {self.current_serial_settings['bytesize']}
Parity: {self.current_serial_settings['parity']}
Stopbits: {self.current_serial_settings['stopbits']}
RS485 Mode: {self.current_serial_settings.get('rs485_mode', False)}
RS485 Address: {self.current_serial_settings.get('rs485_address', 254)}
"""
                self.log_message(settings)

        except Exception as e:
            # Handle any exceptions while retrieving port settings
            self.log_message(f"Error getting port settings: {str(e)}")

    def log_message(self, message: str):
        """
        Add a timestamped message to the output log.

        Args:
            message (str): The message to log.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_frame.append_log(f"[{timestamp}] {message}")

    # ============================
    # Logger Interface Implementation
    # ============================
    def debug(self, message: str):
        """
        Handle debug-level messages by logging them.

        Args:
            message (str): The debug message to log.
        """
        self.log_message(f"DEBUG: {message}")

    def info(self, message: str):
        """
        Handle info-level messages by logging them.

        Args:
            message (str): The info message to log.
        """
        self.log_message(message)

    def warning(self, message: str):
        """
        Handle warning-level messages by logging them.

        Args:
            message (str): The warning message to log.
        """
        self.log_message(f"WARNING: {message}")

    def error(self, message: str):
        """
        Handle error-level messages by logging them.

        Args:
            message (str): The error message to log.
        """
        self.log_message(f"ERROR: {message}")

    def on_closing(self):
        """
        Handle application shutdown by stopping continuous reading,
        disconnecting the communicator, and closing the GUI.
        """
        self.stop_continuous_reading()
        if self.communicator:
            self.communicator.disconnect()
        self.root.destroy()
