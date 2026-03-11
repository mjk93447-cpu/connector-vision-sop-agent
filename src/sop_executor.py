"""
12-step SOP executor for Connector Vision Agent v1.0.

Coordinates login, recipe loading, Mold Left/Right ROI training, axis marking,
In Pin Up/Down verification, and final save/open/apply actions for line setup.
"""

from src.control_engine import ControlEngine
from src.vision_engine import VisionEngine


class SopExecutor:
    """Coordinate the high-level SOP sequence across vision and control layers."""

    def __init__(self, vision: VisionEngine, control: ControlEngine) -> None:
        self.vision = vision
        self.control = control

    def run(self) -> list[str]:
        """Return a placeholder execution trace for the automation flow."""

        targets = self.vision.detect_ui_targets()
        return [self.control.click_target(target) for target in targets]
