"""
GUI/turbo_serial_settings_frame.py

Provides a specialized serial settings frame for Turbo controllers.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class TurboSerialSettingsFrame(ttk.LabelFrame):
    """
    A specialized frame for adjusting Turbo COM parameters including RS485 mode and address.
    """

    def __init__(self, parent: tk.Widget, apply_callback: Callable[[dict], None]) -> None:
        """
        Initialize TurboSerialSettingsFrame.

        Args:
            parent: Parent widget.
            apply_callback: Callback function to call on Apply.
        """
        super().__init__(parent, text="Turbo Serial Config")
        self.apply_callback = apply_callback
        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")
        self.rs485_mode = tk.BooleanVar(value=False)
        self.rs485_addr = tk.StringVar(value="254")
        self._create_widgets()

    def _create_widgets(self) -> None:
        """
        Creates comboboxes for baud, bits, parity, stop bits,
        RS485 controls, and an Apply button.
        """
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(settings_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_combo = ttk.Combobox(settings_frame, textvariable=self.baud_var,
                                  values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
                                  width=7, state="readonly")
        baud_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(settings_frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bits_combo = ttk.Combobox(settings_frame, textvariable=self.bytesize_var,
                                  values=["5", "6", "7", "8"], width=2, state="readonly")
        bits_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(settings_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_combo = ttk.Combobox(settings_frame, textvariable=self.parity_var,
                                    values=["N", "E", "O", "M", "S"], width=2, state="readonly")
        parity_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(settings_frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stop_combo = ttk.Combobox(settings_frame, textvariable=self.stopbits_var,
                                  values=["1", "1.5", "2"], width=3, state="readonly")
        stop_combo.pack(side=tk.LEFT, padx=2)

        rs_frame = ttk.Frame(self)
        rs_frame.pack(fill=tk.X, padx=5, pady=5)
        self.rs485_check = ttk.Checkbutton(rs_frame, text="RS485", variable=self.rs485_mode,
                                           command=self._on_rs485_change)
        self.rs485_check.pack(side=tk.LEFT, padx=5)
        ttk.Label(rs_frame, text="Addr:").pack(side=tk.LEFT, padx=2)
        self.addr_entry = ttk.Entry(rs_frame, textvariable=self.rs485_addr, width=4)
        self.addr_entry.pack(side=tk.LEFT, padx=2)
        self._update_rs485_address_state()

        apply_btn = ttk.Button(self, text="Apply", command=self._on_apply)
        apply_btn.pack(side=tk.RIGHT, padx=5, pady=5)

    def _on_rs485_change(self) -> None:
        """
        Called when RS485 mode is toggled.
        """
        self._update_rs485_address_state()

    def _update_rs485_address_state(self) -> None:
        """
        Enables the RS485 address entry if RS485 is enabled.
        """
        if self.rs485_mode.get():
            self.addr_entry.config(state="normal")
        else:
            self.addr_entry.config(state="disabled")

    def _on_apply(self) -> None:
        """
        Called when the Apply button is pressed.
        Gathers settings and calls the apply_callback.
        """
        settings = {
            "baudrate": int(self.baud_var.get()),
            "bytesize": int(self.bytesize_var.get()),
            "parity": self.parity_var.get(),
            "stopbits": float(self.stopbits_var.get()),
            "rs485_mode": self.rs485_mode.get(),
            "rs485_address": int(self.rs485_addr.get()) if self.rs485_mode.get() else None
        }
        self.apply_callback(settings)
