"""Desktop GUI entrypoint and application runner for JARVIS."""

import sys
from typing import Optional
from PyQt6.QtWidgets import QApplication

from app.core.logger import setup_logger
from app.core.orchestrator import Orchestrator
from app.ui.main_window import JarvisMainWindow

logger = setup_logger("jarvis.ui.app")


def run_gui(orchestrator: Optional[Orchestrator] = None) -> int:
    """Launches the PyQt6 Desktop GUI Dashboard."""
    logger.info("Starting JARVIS Graphical User Interface (GUI)...")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName("JARVIS")
    app.setOrganizationName("JARVIS-AI")

    window = JarvisMainWindow(orchestrator=orchestrator)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
