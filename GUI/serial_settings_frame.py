# GUI/serial_settings_frame.py

"""
SerialSettingsFrame: Manages RS232/RS485 settings and manual command input.
Provides UI elements to configure serial parameters and send arbitrary commands.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

class SerialSettingsFrame(ttk.LabelFrame):
    """
    Frame for controlling RS232/RS485 serial port settings and manual command entry.
    Provides UI elements to configure serial parameters and send arbitrary commands.
    """

    def __init__(self, parent, settings_callback: Callable, command_callback: Callable):
        """
        Initializes the SerialSettingsFrame with callbacks for settings changes and manual commands.

        Args:
            parent: Parent widget
            settings_callback: Function to call when settings change
            command_callback: Function to call for manual commands
        """
        super().__init__(parent, text="Serial Settings & Manual Command")

        # Stores callback functions passed from parent
        self.settings_callback = settings_callback
        self.command_callback = command_callback

        # Parent application that provides logging (set later)
        self.parent_app = None

        # Holds the user-selected baud rate
        self.baud_var = tk.StringVar(value="9600")
        # Holds the number of data bits
        self.bytesize_var = tk.StringVar(value="8")
        # Holds the parity setting
        self.parity_var = tk.StringVar(value="N")
        # Holds the stop bits
        self.stopbits_var = tk.StringVar(value="1")
        # Tracks if RS485 mode is enabled
        self.rs485_mode = tk.BooleanVar(value=False)
        # Holds the RS485 address if in RS485 mode
        self.rs485_addr = tk.StringVar(value="254")

        # Stores command history for up/down recall
        self.cmd_history = []
        self.history_index = -1

        # Builds the frame's widgets
        self._create_widgets()

    def _create_widgets(self):
        """
        Creates all widgets for serial settings in a single row:
        - Basic serial settings (baud, bits, parity, stop)
        - RS485 settings (mode toggle, address)
        - Apply button
        """
        # Creates frame for settings
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # Left side: basic serial settings
        left_frame = ttk.Frame(settings_frame)
        left_frame.pack(side=tk.LEFT, padx=5)

        # Adds baud rate control
        ttk.Label(left_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_menu = ttk.Combobox(
            left_frame,
            textvariable=self.baud_var,
            values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
            width=7
        )
        baud_menu.pack(side=tk.LEFT, padx=2)

        # Adds data bits control
        ttk.Label(left_frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bytesize_menu = ttk.Combobox(
            left_frame,
            textvariable=self.bytesize_var,
            values=["5", "6", "7", "8"],
            width=2
        )
        bytesize_menu.pack(side=tk.LEFT, padx=2)

        # Center: parity and stop bits
        center_frame = ttk.Frame(settings_frame)
        center_frame.pack(side=tk.LEFT, padx=5)

        # Adds parity control
        ttk.Label(center_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_menu = ttk.Combobox(
            center_frame,
            textvariable=self.parity_var,
            values=["N", "E", "O", "M", "S"],
            width=2
        )
        parity_menu.pack(side=tk.LEFT, padx=2)

        # Adds stop bits control
        ttk.Label(center_frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stopbits_menu = ttk.Combobox(
            center_frame,
            textvariable=self.stopbits_var,
            values=["1", "1.5", "2"],
            width=3
        )
        stopbits_menu.pack(side=tk.LEFT, padx=2)

        # Right side: RS485 settings
        right_frame = ttk.Frame(settings_frame)
        right_frame.pack(side=tk.LEFT, padx=5)

        # Creates RS485 controls frame
        rs485_frame = ttk.Frame(right_frame)
        rs485_frame.pack(side=tk.LEFT, padx=2)

        # Adds RS485 mode checkbox
        self.rs485_check = ttk.Checkbutton(
            rs485_frame,
            text="RS485",
            variable=self.rs485_mode,
            command=self._on_rs485_change
        )
        self.rs485_check.pack(side=tk.LEFT, padx=2)

        # Adds RS485 address entry
        ttk.Label(rs485_frame, text="Addr:").pack(side=tk.LEFT, padx=2)
        self.rs485_addr_entry = ttk.Entry(rs485_frame, textvariable=self.rs485_addr, width=4)
        self.rs485_addr_entry.pack(side=tk.LEFT, padx=2)

        # Adds Apply button
        ttk.Button(right_frame, text="Apply", command=self.apply_settings, width=8).pack(side=tk.LEFT, padx=5)

        # Updates RS485 address state based on mode
        self._update_rs485_address_state()

    def _update_rs485_address_state(self):
        """Enables or disables RS485 address entry depending on RS485 mode"""
        state = 'normal' if self.rs485_mode.get() else 'disabled'
        self.rs485_addr_entry.configure(state=state)

    def _on_rs485_change(self):
        """
        Called when user toggles RS485 checkbox.
        Updates address entry state and applies new settings.
        """
        self._update_rs485_address_state()
        settings = self.get_current_settings()
        self.settings_callback(settings)

    def get_current_settings(self) -> dict:
        """
        Gets current serial settings from UI controls.

        Returns:
            dict: Current serial settings
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
        Called when Apply button clicked.
        Gets current settings and sends to parent callback.
        """
        # Gets current settings
        settings = self.get_current_settings()

        # Calls parent's settings callback
        self.settings_callback(settings)

        # Creates formatted settings message
        settings_msg = (
            f"\nSerial settings applied:\n"
            f"Baud Rate: {settings['baudrate']}\n"
            f"Data Bits: {settings['bytesize']}\n"
            f"Parity: {settings['parity']}\n"
            f"Stop Bits: {settings['stopbits']}\n"
        )

        # Adds RS485 settings if enabled
        if settings['rs485_mode']:
            settings_msg += (
                f"RS485 Mode: Enabled\n"
                f"RS485 Address: {settings['rs485_address']}\n"
            )
        else:
            settings_msg += f"RS485 Mode: Disabled\n"

        # Logs settings changes using parent's log_message method
        if self.parent_app:
            self.parent_app.log_message(settings_msg)

    def set_parent(self, parent_app):
        """
        Sets reference to parent application for logging.

        Args:
            parent_app: Parent application instance
        """
        self.parent_app = parent_app

    def set_rs485_mode(self, enabled: bool, address: int = 254):
        """
        Enables or disables RS485 mode externally.
        Called when switching gauges.

        Args:
            enabled: Whether to enable RS485 mode
            address: RS485 address to use if enabled
        """
        self.rs485_mode.set(enabled)
        self.rs485_addr.set(str(address))
        self._update_rs485_address_state()
        self._on_rs485_change()

    def send_command(self, event=None):
        """
        Sends a manual command from entry.
        Called when user hits Enter or clicks Send.
        """
        cmd = self.manual_cmd_entry.get().strip()
        if cmd:
            self.command_callback(cmd)
            self.manual_cmd_entry.delete(0, tk.END)
            if not self.cmd_history or self.cmd_history[-1] != cmd:
                self.cmd_history.append(cmd)
            self.history_index = len(self.cmd_history)

    def history_up(self, event):
        """Recalls previous command from history"""
        if self.cmd_history and self.history_index > 0:
            self.history_index -= 1
            self.manual_cmd_entry.delete(0, tk.END)
            self.manual_cmd_entry.insert(0, self.cmd_history[self.history_index])

    def history_down(self, event):
        """Recalls next command from history"""
        if self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self.manual_cmd_entry.delete(0, tk.END)
            self.manual_cmd_entry.insert(0, self.cmd_history[self.history_index])

    def set_enabled(self, enabled: bool):
        """
        Enables or disables all widgets.
        Called when connecting/disconnecting.

        Args:
            enabled: Whether to enable the widgets
        """
        state = "normal" if enabled else "disabled"
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                child.configure(state=state)