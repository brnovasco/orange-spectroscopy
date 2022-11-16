from PyQt5.QtWidgets import QVBoxLayout
from Orange.widgets import gui

from orangecontrib.spectroscopy.preprocess import PhaseUnwrap
from orangecontrib.spectroscopy.widgets.gui import lineEditFloatRange
from orangecontrib.spectroscopy.widgets.preprocessors.registry import \
    preprocess_editors
from orangecontrib.spectroscopy.widgets.preprocessors.utils import \
    BaseEditorOrange

# from PyQt5.QtWidgets import QFormLayout



class PhaseUnwrapEditor(BaseEditorOrange):
    """
    Phase Unwrap.
    """
    name = "Phase Unwrap"
    qualname = "orangecontrib.infrared.phaseunwrap"  

    UNWRAP_DEFAULT = True

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.controlArea.setLayout(QVBoxLayout())

        self.unwrap = self.UNWRAP_DEFAULT
        gui.checkBox(self.controlArea, self, "unwrap", "Unwrap", callback=self.edited.emit)

        # form = QFormLayout()
        # amounte = lineEditFloatRange(self, self, "amount", callback=self.edited.emit)
        # form.addRow("Shift Amount", amounte)
        # self.controlArea.setLayout(form)

    def setParameters(self, params):
        self.unwrap = params.get("unwrap", self.UNWRAP_DEFAULT)

    @classmethod
    def createinstance(cls, params):
        params = dict(params)
        unwrap = params.get("unwrap", cls.UNWRAP_DEFAULT)
        return PhaseUnwrap(unwrap=unwrap)


preprocess_editors.register(PhaseUnwrapEditor, 1000)
