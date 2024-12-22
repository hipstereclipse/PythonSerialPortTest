"""
SerialSettingsFrame: Manages RS232/RS485 settings and manual command input.
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
        Initializes the SerialSettingsFrame with callbacks for:
         - settings changes (settings_callback)
         - manual commands (command_callback)
        """
        super().__init__(parent, text="Serial Settings & Manual Command")

        self.settings_callback = settings_callback
        self.command_callback = command_callback
        self.logger = None  # Will be set using set_logger()

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

        # A simple list to store manual command history (not fully implemented)
        self.cmd_history = []
        self.history_index = -1

        # Builds the frame's widgets
        self._create_widgets()

    def set_logger(self, logger):
        """
        Assigns a logger instance for writing logs if needed.
        """
        self.logger = logger

    def _create_widgets(self):
        """
        Creates all widgets for serial settings in a single row.
        """
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # Left side: basic serial settings
        left_frame = ttk.Frame(settings_frame)
        left_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(left_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_menu = ttk.Combobox(
            left_frame,
            textvariable=self.baud_var,
            values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
            width=7
        )
        baud_menu.pack(side=tk.LEFT, padx=2)

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

        ttk.Label(center_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_menu = ttk.Combobox(
            center_frame,
            textvariable=self.parity_var,
            values=["N", "E", "O", "M", "S"],
            width=2
        )
        parity_menu.pack(side=tk.LEFT, padx=2)

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

        rs485_frame = ttk.Frame(right_frame)
        rs485_frame.pack(side=tk.LEFT, padx=2)

        self.rs485_check = ttk.Checkbutton(
            rs485_frame,
            text="RS485",
            variable=self.rs485_mode,
            command=self._on_rs485_change
        )
        self.rs485_check.pack(side=tk.LEFT, padx=2)

        ttk.Label(rs485_frame, text="Addr:").pack(side=tk.LEFT, padx=2)
        self.rs485_addr_entry = ttk.Entry(rs485_frame, textvariable=self.rs485_addr, width=4)
        self.rs485_addr_entry.pack(side=tk.LEFT, padx=2)

        # A button to apply these settings
        ttk.Button(right_frame, text="Apply", command=self.apply_settings, width=8).pack(side=tk.LEFT, padx=5)

        # Reflects whether the RS485 address is enabled/disabled
        self._update_rs485_address_state()

    def _update_rs485_address_state(self):
        """
        Enables or disables RS485 address entry depending on RS485 mode.
        """
        state = 'normal' if self.rs485_mode.get() else 'disabled'
        self.rs485_addr_entry.configure(state=state)

    def _on_rs485_change(self):
        """
        Called when the user toggles the "RS485" checkbox.
        Updates the UI and calls the settings callback.
        """
        self._update_rs485_address_state()
        settings = self.get_current_settings()
        self.settings_callback(settings)

    def get_current_settings(self) -> dict:
        """
        Returns the current user-selected serial settings in dictionary form.
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
        Called when the user clicks "Apply" to confirm the new serial settings.
        """
        settings = self.get_current_settings()
        self.settings_callback(settings)

        # Logs a message listing the new settings
        settings_msg = (
            f"\nSerial settings applied:\n"
            f"Baud Rate: {settings['baudrate']}\n"
            f"Data Bits: {settings['bytesize']}\n"
            f"Parity: {settings['parity']}\n"
            f"Stop Bits: {settings['stopbits']}\n"
        )
        if settings['rs485_mode']:
            settings_msg += (
                f"RS485 Mode: Enabled\n"
                f"RS485 Address: {settings['rs485_address']}\n"
            )
        else:
            settings_msg += f"RS485 Mode: Disabled\n"

        if self.logger:
            self.logger.info(settings_msg)

    def set_rs485_mode(self, enabled: bool, address: int = 254):
        """
        Enables or disables RS485 mode externally, e.g. when switching gauges.
        """
        self.rs485_mode.set(enabled)
        self.rs485_addr.set(str(address))
        self._update_rs485_address_state()
        self._on_rs485_change()

    # Placeholder methods for manual command entry (if needed).
    def send_command(self, event=None):
        pass

    def history_up(self, event):
        pass

    def history_down(self, event):
        pass
