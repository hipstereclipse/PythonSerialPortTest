#!/usr/bin/env python3
"""
Main entry point for the Gauge Communication Program.
Initializes the GUI and starts the application.
"""

import sys
import tkinter as tk
from tkinter import messagebox
import logging
from pathlib import Path

from GUI.main_app import GaugeApplication
from serial_communication.config import setup_logging


def setup_exception_handling(root, logger):
    """Configure global exception handler to log errors and show user-friendly messages."""
    def show_error(msg):
        """Show error dialog to user."""
        messagebox.showerror("Error", f"An error occurred: {msg}\n\nCheck the log for details.")

    def handle_exception(exc_type, exc_value, exc_traceback):
        """Log unhandled exceptions and show dialog."""
        if issubclass(exc_type, KeyboardInterrupt):
            root.quit()
            return

        logger.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        root.after(100, lambda: show_error(str(exc_value)))

    # Set up logging
    sys.excepthook = handle_exception

def create_app_directories():
    """Create necessary application directories if they don't exist."""
    app_dir = Path.home() / ".gauge_communicator"
    log_dir = app_dir / "logs"
    config_dir = app_dir / "config"

    for directory in [app_dir, log_dir, config_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return app_dir, log_dir, config_dir

def main():
    """Main entry point of the application."""
    # Create application directories
    app_dir, log_dir, config_dir = create_app_directories()

    # Initialize logging
    logger = setup_logging("GaugeCommunicator")
    logger.info("Starting Gauge Communication Program")

    # Create main window
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, app))

    # Setup exception handling
    setup_exception_handling(root, logger)

    try:
        # Initialize main application
        app = GaugeApplication(root)
        logger.info("Application initialized successfully")

        # Center window on screen
        window_width = 800
        window_height = 650
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

        # Start the application
        root.mainloop()

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        messagebox.showerror("Startup Error",
                           f"Failed to start application: {str(e)}\n\nCheck the log for details.")
        sys.exit(1)

def on_closing(root, app):
    """Handle application shutdown."""
    try:
        app.on_closing()
    except Exception as e:
        logging.error(f"Error during shutdown: {str(e)}", exc_info=True)
    finally:
        root.destroy()

if __name__ == "__main__":
    main()