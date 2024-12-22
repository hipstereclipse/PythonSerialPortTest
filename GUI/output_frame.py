"""
output_frame.py

This module implements the OutputFrame class which handles display of log messages
and command responses. It supports:
- Message filtering for debug vs non-debug content
- Output format selection
- Scrollable text display
- Message history tracking
"""

import tkinter as tk
from tkinter import ttk
from serial_communication.config import OUTPUT_FORMATS

class OutputFrame(ttk.LabelFrame):
    """
    Frame for displaying command outputs and response logs.
    Provides format selection and debug message filtering.
    """

    def __init__(self, parent, output_format: tk.StringVar):
        """
        Creates and configures the output display frame.
        Args:
            parent: Parent widget (usually main window)
            output_format: StringVar tracking selected output format
        """
        super().__init__(parent, text="Output")

        # Stores reference to format variable
        self.output_format = output_format

        # List to track all messages for filtering
        self.messages = []

        # Creates format selection controls
        format_frame = ttk.Frame(self)
        format_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds format label and dropdown
        ttk.Label(format_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            format_frame,
            self.output_format,
            "ASCII",
            *OUTPUT_FORMATS
        ).pack(side=tk.LEFT, padx=5)

        # Creates scrollable text area for output
        self.output_text = tk.Text(
            self,
            height=20,
            width=80,
            wrap=tk.WORD  # Wraps text at word boundaries
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Adds vertical scrollbar
        scrollbar = ttk.Scrollbar(
            self.output_text,
            orient="vertical",
            command=self.output_text.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Links scrollbar to text widget
        self.output_text.config(yscrollcommand=scrollbar.set)

    def append_log(self, message: str):
        """
        Adds a new message to both storage and display.
        Args:
            message: Text to add to log
        """
        # Stores message in history
        self.messages.append(message)

        # Adds to display with newline
        self.output_text.insert(tk.END, message + "\n")

        # Scrolls to show new message
        self.output_text.see(tk.END)

    def clear(self):
        """
        Removes all content from both storage and display.
        """
        # Clears message history
        self.messages.clear()

        # Clears display widget
        self.output_text.delete(1.0, tk.END)

    def filter_debug_messages(self, show_debug: bool):
        """
        Updates the output display to show or hide debug messages based on the state.
        Args:
            show_debug: Whether to display debug (`True`) or hide them (`False`).
        """
        # Clear the current display
        self.output_text.delete(1.0, tk.END)

        # Iterate through stored messages and filter based on debug visibility
        for msg in self.messages:
            if show_debug or not ("DEBUG" in msg):
                self.output_text.insert(tk.END, msg + "\n")

        # Keep the scroll at the end after updating
        self.output_text.see(tk.END)
