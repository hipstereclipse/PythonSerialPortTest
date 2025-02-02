#!/usr/bin/env python3
"""
simulator_panel.py

This module implements the SimulatorPanel class, a GUI panel that allows the user to configure
the DeviceSimulator parameters. Users can select which gauge types to simulate, adjust dynamic
value ranges, noise level, response delays, and manually trigger error states.

Usage Example:
    from simulator_panel import SimulatorPanel
    panel = SimulatorPanel(parent, current_config, callback)
    panel.pack()

    - current_config is a dict with keys such as "gauge_type", "pressure_range", etc.
    - callback is a function that receives the new configuration dict.
"""

import tkinter as tk
from tkinter import ttk


class SimulatorPanel(ttk.LabelFrame):
    """
    Provides a control panel to configure the hardware simulator.
    """

    def __init__(self, parent, current_config: dict, apply_callback, **kwargs):
        """
        Initializes the SimulatorPanel.

        Args:
            parent: Parent widget.
            current_config (dict): Current simulation configuration.
            apply_callback (callable): Function to call when applying new configuration.
        """
        super().__init__(parent, text="Simulator Configuration", **kwargs)
        self.current_config = current_config
        self.apply_callback = apply_callback
        self._build_widgets()

    def _build_widgets(self):
        # Gauge Type Dropdown
        ttk.Label(self, text="Gauge Type:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.gauge_type_var = tk.StringVar(value=self.current_config.get("gauge_type", "PPG550"))
        gauge_types = ["PPG550", "PPG570", "CDG025D", "CDG045D", "MPG500"]  # Extend as needed
        gauge_menu = ttk.Combobox(self, textvariable=self.gauge_type_var, values=gauge_types, state="readonly")
        gauge_menu.grid(row=0, column=1, padx=5, pady=5)

        # Pressure Range
        ttk.Label(self, text="Pressure Range (min, max):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.pressure_min_var = tk.StringVar(value=str(self.current_config.get("pressure_range", (0.1, 1000))[0]))
        self.pressure_max_var = tk.StringVar(value=str(self.current_config.get("pressure_range", (0.1, 1000))[1]))
        ttk.Entry(self, textvariable=self.pressure_min_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(self, textvariable=self.pressure_max_var, width=10).grid(row=1, column=2, padx=5, pady=5, sticky="w")

        # Temperature Range
        ttk.Label(self, text="Temperature Range (min, max):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.temp_min_var = tk.StringVar(value=str(self.current_config.get("temp_range", (-50, 300))[0]))
        self.temp_max_var = tk.StringVar(value=str(self.current_config.get("temp_range", (-50, 300))[1]))
        ttk.Entry(self, textvariable=self.temp_min_var, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(self, textvariable=self.temp_max_var, width=10).grid(row=2, column=2, padx=5, pady=5, sticky="w")

        # Noise Level
        ttk.Label(self, text="Noise Level (fraction):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.noise_var = tk.StringVar(value=str(self.current_config.get("noise_level", 0.05)))
        ttk.Entry(self, textvariable=self.noise_var, width=10).grid(row=3, column=1, padx=5, pady=5, sticky="w")

        # Response Delay
        ttk.Label(self, text="Response Delay (s):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.delay_var = tk.StringVar(value=str(self.current_config.get("response_delay", 0.1)))
        ttk.Entry(self, textvariable=self.delay_var, width=10).grid(row=4, column=1, padx=5, pady=5, sticky="w")

        # Error Probability
        ttk.Label(self, text="Error Probability:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.error_prob_var = tk.StringVar(value=str(self.current_config.get("error_probability", 0.0)))
        ttk.Entry(self, textvariable=self.error_prob_var, width=10).grid(row=5, column=1, padx=5, pady=5, sticky="w")

        # Apply Button
        ttk.Button(self, text="Apply", command=self._apply).grid(row=6, column=0, columnspan=3, padx=5, pady=10)

    def _apply(self):
        try:
            new_config = {
                "gauge_type": self.gauge_type_var.get(),
                "pressure_range": (float(self.pressure_min_var.get()), float(self.pressure_max_var.get())),
                "temp_range": (float(self.temp_min_var.get()), float(self.temp_max_var.get())),
                "noise_level": float(self.noise_var.get()),
                "response_delay": float(self.delay_var.get()),
                "error_probability": float(self.error_prob_var.get())
            }
            self.apply_callback(new_config)
        except Exception as e:
            print(f"Error applying simulation configuration: {e}")
