import numpy as np
import pyqtgraph as pg

from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import (
    QComboBox, QSpinBox, QVBoxLayout, QFormLayout, QSizePolicy, QLabel
)
from AnyQt.QtGui import QColor

from Orange.widgets import gui
from Orange.widgets.widget import Msg
from Orange.widgets.data.owpreprocess import blocked

from orangecontrib.spectroscopy.data import getx

from orangecontrib.spectroscopy.preprocess import Cut, ManualTilt

from orangecontrib.spectroscopy.preprocess.transform import SpecTypes
from orangecontrib.spectroscopy.widgets.gui import lineEditFloatRange, MovableVline, \
    connect_line, floatornone, round_virtual_pixels
from orangecontrib.spectroscopy.widgets.preprocessors.utils import BaseEditor, BaseEditorOrange, \
    REFERENCE_DATA_PARAM
from orangecontrib.spectroscopy.widgets.preprocessors.registry import preprocess_editors

class ManualEditor(BaseEditorOrange):
    """
    Editor for Cut
    """
    name = "Manual Editor"
    qualname = "orangecontrib.infrared.manualeditor"

    class Warning(BaseEditorOrange.Warning):
        out_of_range = Msg("Limits are out of range.")

    def __init__(self, parent=None, **kwargs):
        BaseEditorOrange.__init__(self, parent, **kwargs)

        self.lowlim = 0.
        self.highlim = 1.

        layout = QFormLayout()
        self.controlArea.setLayout(layout)

        # self._lowlime = lineEditFloatRange(self, self, "lowlim", callback=self.edited.emit)
        self._highlime = lineEditFloatRange(self, self, "highlim", callback=self.edited.emit)

        # layout.addRow("Low limit", self._lowlime)
        layout.addRow("High limit", self._highlime)

        # self._lowlime.focusIn.connect(self.activateOptions)
        self._highlime.focusIn.connect(self.activateOptions)
        self.focusIn = self.activateOptions

        # self.line1 = MovableVline(label="Low limit")
        # connect_line(self.line1, self, "lowlim")
        # self.line1.sigMoveFinished.connect(self.edited)
        self.line2 = MovableVline(label="High limit")
        connect_line(self.line2, self, "highlim")
        self.line2.sigMoveFinished.connect(self.edited)

        self.user_changed = False

    def activateOptions(self):
        self.parent_widget.curveplot.clear_markings()

        # for line in [self.line1, self.line2]:
        #     line.report = self.parent_widget.curveplot
        #     self.parent_widget.curveplot.add_marking(line) 

        self.line2.report = self.parent_widget.curveplot
        self.parent_widget.curveplot.add_marking(self.line2) #### hereeeeeeeeeeeeeeeee <<<<<<<<<

    def setParameters(self, params):
        if params: #parameters were manually set somewhere else
            self.user_changed = True
        # self.lowlim = params.get("lowlim", 0.)
        self.highlim = params.get("highlim", 1.)

    @staticmethod
    def createinstance(params):
        params = dict(params)
        lowlim = params.get("lowlim", None)
        highlim = params.get("highlim", None)
        return Cut(lowlim=floatornone(lowlim), highlim=floatornone(highlim))
        # return ManualTilt() # changeThis? or just send x pos? (2nd option is preferable)

    def set_preview_data(self, data):
        self.Warning.out_of_range.clear()
        x = getx(data)
        if len(x):
            minx = np.min(x)
            maxx = np.max(x)
            range = maxx - minx

            init_lowlim = round_virtual_pixels(minx + 0.1 * range, range)
            init_highlim = round_virtual_pixels(maxx - 0.1 * range, range)

            # self._lowlime.set_default(init_lowlim)
            self._highlime.set_default(init_highlim)

            if not self.user_changed:
                # self.lowlim = init_lowlim
                self.highlim = init_highlim
                self.edited.emit()

            if (self.lowlim < minx and self.highlim < minx) \
                    or (self.lowlim > maxx and self.highlim > maxx):
                self.parent_widget.Warning.preprocessor()
                self.Warning.out_of_range()


preprocess_editors.register(ManualEditor, 1075)
