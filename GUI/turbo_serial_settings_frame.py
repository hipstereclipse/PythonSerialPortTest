"""
turbo_serial_settings_frame.py
Provides a specialized serial settings frame for Turbo, with RS485 toggles
similar to your gauge's serial settings approach.

Features:
 - Baud, data bits, parity, stop bits comboboxes
 - RS485 mode checkbox, RS485 address entry
 - "Apply" button that calls an apply_callback(settings_dict)
Uses thorough, active-voice comments on almost every line as requested.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class TurboSerialSettingsFrame(ttk.LabelFrame):
    """
    TurboSerialSettingsFrame:
    A specialized frame for adjusting Turbo COM parameters, including RS485 mode
    and address, similar to your gauge's serial settings frame.
    """

    def __init__(self, parent, apply_callback: Callable[[dict], None]):
        """
        Initializes the frame with all serial settings controls:
         - baud, data bits, parity, stop bits
         - RS485 mode checkbox, address
         - an "Apply" button that calls apply_callback(settings_dict).
        parent        : the parent widget (TurboFrame or container)
        apply_callback: function to call when user clicks "Apply,"
                        passing a dict of new settings
        """
        # Creates a labeled frame titled "Turbo Serial Config"
        super().__init__(parent, text="Turbo Serial Config")

        # Stores the callback
        self.apply_callback = apply_callback

        # Creates StringVars/BooleanVars for each setting
        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")

        # Adds RS485 toggles
        self.rs485_mode = tk.BooleanVar(value=False)
        self.rs485_addr = tk.StringVar(value="254")

        # Builds the UI
        self._create_widgets()

    def _create_widgets(self):
        """
        Creates comboboxes for baud, bits, parity, stop bits,
        plus an RS485 checkbox & address field, and an "Apply" button.
        """
        # Adds a frame to hold the main layout
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # Builds row for basic serial settings
        # Baud
        ttk.Label(settings_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.baud_var,
            values=["1200","2400","4800","9600","19200","38400","57600","115200"],
            width=7,
            state="readonly"
        )
        baud_combo.pack(side=tk.LEFT, padx=2)

        # Data bits
        ttk.Label(settings_frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bits_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.bytesize_var,
            values=["5","6","7","8"],
            width=2,
            state="readonly"
        )
        bits_combo.pack(side=tk.LEFT, padx=2)

        # Parity
        ttk.Label(settings_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.parity_var,
            values=["N","E","O","M","S"],
            width=2,
            state="readonly"
        )
        parity_combo.pack(side=tk.LEFT, padx=2)

        # Stop bits
        ttk.Label(settings_frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stop_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.stopbits_var,
            values=["1","1.5","2"],
            width=3,
            state="readonly"
        )
        stop_combo.pack(side=tk.LEFT, padx=2)

        # Creates a separate row for RS485 controls
        rs_frame = ttk.Frame(self)
        rs_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds an RS485 mode checkbox
        self.rs485_check = ttk.Checkbutton(
            rs_frame,
            text="RS485",
            variable=self.rs485_mode,
            command=self._on_rs485_change
        )
        self.rs485_check.pack(side=tk.LEFT, padx=5)

        # Adds a label "Addr:" and an Entry for the address
        ttk.Label(rs_frame, text="Addr:").pack(side=tk.LEFT, padx=2)
        self.addr_entry = ttk.Entry(rs_frame, textvariable=self.rs485_addr, width=4)
        self.addr_entry.pack(side=tk.LEFT, padx=2)

        # Calls _update_rs485_address_state once initially
        self._update_rs485_address_state()

        # Adds an "Apply" button at the bottom
        apply_btn = ttk.Button(
            self,
            text="Apply",
            command=self._on_apply
        )
        apply_btn.pack(side=tk.RIGHT, padx=5, pady=5)

    def _on_rs485_change(self):
        """
        Called when the user toggles the RS485 checkbox,
        so we can enable/disable the address entry.
        """
        self._update_rs485_address_state()

    def _update_rs485_address_state(self):
        """
        Enables the address entry if RS485 is on,
        disables it if RS485 is off.
        """
        if self.rs485_mode.get():
            self.addr_entry.config(state="normal")
        else:
            self.addr_entry.config(state="disabled")

    def _on_apply(self):
        """
        Called when user clicks "Apply."
        We build a settings dict with all chosen values
        including RS485 mode and address, then call apply_callback.
        """
        # Gathers the settings
        settings = {
            "baudrate": int(self.baud_var.get()),
            "bytesize": int(self.bytesize_var.get()),
            "parity": self.parity_var.get(),
            "stopbits": float(self.stopbits_var.get()),
            "rs485_mode": self.rs485_mode.get(),
            "rs485_address": int(self.rs485_addr.get()) if self.rs485_mode.get() else None
        }

        # Calls the callback with the newly built settings
        self.apply_callback(settings)
