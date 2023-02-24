import sys
import numpy as np
import pyqtgraph as pg
from decimal import Decimal

import Orange.data

from AnyQt.QtCore import Qt, QRectF, QPointF, QSize
from AnyQt.QtTest import QTest
from AnyQt.QtWidgets import QWidget, QPushButton, QGridLayout, QFormLayout, QAction, QVBoxLayout, QWidgetAction, QSplitter, QToolTip, QGraphicsRectItem

from Orange.data import Domain
from Orange.widgets import gui, settings
from Orange.widgets.widget import OWWidget, Input, Output, OWBaseWidget, Msg
from Orange.widgets.settings import Setting, ContextSetting, DomainContextHandler, SettingProvider
from Orange.widgets.utils.concurrent import TaskState, ConcurrentWidgetMixin, ConcurrentMixin
from orangecontrib.spectroscopy.widgets.preprocessors.utils import SetXDoubleSpinBox
from orangecontrib.spectroscopy.preprocess.utils import SelectColumn
from orangecontrib.spectroscopy.util import getx
from orangecontrib.spectroscopy.widgets.gui import MovableHline, lineEditFloatRange, floatornone, MovableVline, lineEditDecimalOrNone,\
    pixels_to_decimals, float_to_str_decimals
from orangecontrib.spectroscopy.widgets.owspectra import CurvePlot
from orangecontrib.spectroscopy.preprocess import Cut,  ManualTilt



class OWManualEditor(OWWidget, ConcurrentWidgetMixin):
    """
    Manual Editor
    """

    name = "ManualEditor"

    class Inputs:
        data = Input("Data", Orange.data.Table, default=True)

    class Outputs:
        data_edited = Output("Edited Data", Orange.data.Table, default=True)

    icon = "icons/hyper.svg"
    priority = 200 # change this number to an appropriate one
    keywords = ["image", "spectral", "chemical", "imaging"]

    settings_version = 6
    settingsHandler = DomainContextHandler()

    plot_in = SettingProvider(CurvePlot)
    plot_out = SettingProvider(CurvePlot)

    lowlim = Setting(None)
    highlim = Setting(None)

    autocommit = settings.Setting(True)

    class Warning(OWBaseWidget.Warning):
        out_of_range = Msg("Limits are out of range.")

    def __init__(self):
        super().__init__()
        ConcurrentWidgetMixin.__init__(self)

        self.data = None
        self.lowlim = 0.
        self.highlim = 0.
        self.slope = 0.

        box = gui.widgetBox(self.controlArea, "Map grid")

        gui.spin(box, self, "slope", 0., sys.float_info.max, step=0.001, label="Slope Spin",
                 callback=self._spin_update_slope, spinType=float)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Vertical)

        self.plot_in = CurvePlot(self)
        self.plot_out = CurvePlot(self)
        self.plot_in.plot.vb.x_padding = 0.1005  # pad view so that lines are not hidden
        self.plot_out.plot.vb.y_padding = 0.1005  # pad view so that lines are not hidden

        splitter.addWidget(self.plot_in)
        splitter.addWidget(self.plot_out)

        self.mainArea.layout().addWidget(splitter)
        def rounded(line):
            return float(line.rounded_value())
        
        self.refLine = MovableHline(position=self.highlim, label="", report=self.plot_in)
        self.refLine.sigMoved.connect(lambda _: self.moveLine(rounded(self.refLine)))
        self.plot_in.add_marking(self.refLine)

        color=(225, 0, 0)

        pen = pg.mkPen(color=color, width=2)
        

        self.diagonalLine = pg.InfiniteLine(angle=self._in_degrees(self.slope), pen=pen, hoverPen=None, movable=False, span=(0, 2))
        self.plot_in.add_marking(self.diagonalLine)

        self.user_changed = False
        # self.plot_in.show()
        # self.plot_out.show()

        gui.auto_commit(self.controlArea, self, "autocommit", "Send Data")
        self._change_input()

    def _in_degrees(self, slope):
        return np.degrees(np.arctan(float(slope)))

    def _change_input(self):
        self.commit.deferred()

    def activateOptions(self):
        print(">>>> on activateOptions")
        self.plot_in.clear_markings() 
        self.plot_out.clear_markings()
        self.refLine.report = self.plot_in
        self.plot_in.add_marking(self.refLine)
        self.plot_in.add_marking(self.diagonalLine)

    @Inputs.data
    def set_data(self, data):
        print(">>>> on set_data (Input)")
        self.data = data
        self.plot_in.set_data(data)
        self._init_slope()

    def on_done(self, out_data):
        print(">>>> on_done")
        self.plot_out.set_data(out_data) # set data to plot_out
        self.Outputs.data_edited.send(out_data) # send data to Output

    def _update_lines(self):
        print(">>>> updating lines", self._in_degrees(self.slope))
        self.refLine.setValue(self.highlim)
        self.diagonalLine.setAngle(self._in_degrees(self.slope))

    def _init_slope(self):
        data_array = self.data.X
        data_max, data_min = np.max(data_array), np.min(data_array) 
        print(">>>>> init slope: setting new value to highlim from  = {} + {} /2".format(data_max, data_min))
        self.highlim = (data_max + data_min)/2
        self.update_slope()
        self._update_lines()
        self.activateOptions()

    def _calculate_slope(self):
        print(">>>> calculate_slope")
        xax = getx(self.data)
        x_max, x_0 = xax[-1], xax[0]
        sloperads = (self.highlim - self.lowlim) / (x_max - x_0) 
        return sloperads

    def update_slope(self):
        print(">>>> update_slope")
        # when the line position is changed, changes the slope value
        if self.data is not None:
            self.slope = Decimal(self._calculate_slope())
            self._update_lines()
            print(">>>>> line update: setting new value to slope = {} with highlim {}".format(self.slope, self.highlim))
        else:
            self.slope = 0.
        self.commit.deferred()

    def _spin_update_slope(self):
        print(">>>> _spin_update_slope")
        # when slope is manually changed, changes the line position
        if self.data is not None:
            xax = getx(self.data)
            x_max, x_0 = xax[-1], xax[0]
            self.highlim = Decimal(self.slope * (x_max - x_0))
            print(">>>>> spin update: setting new value to highlim = {} with slope {}".format(self.highlim, self.slope))
            # self.refLine.setValue(self.highlim)
            self._update_lines()
            self.activateOptions()
        else:
            self.slope = 0.
            self._update_lines()
        self.commit.deferred()
    
    def moveLine(self, value, user=True):
        print(">>>> moveLine")
        if user:
            self.user_changed = True
        if self.highlim != value:
            self.highlim = value
            self.update_slope()

    @gui.deferred
    def commit(self):
        print(">>>> on commit")
        if self.data is not None:
            # calculate out_data
            out_data = ManualTilt(lowlim=floatornone(self.lowlim), highlim=floatornone(self.highlim))(self.data)
            self.on_done(out_data)

    def handleNewSignals(self):
        print(">>>> on handleNewSignals")
        self.commit.deferred()

    # @staticmethod
    # def createinstance(params):
    #     print("createinstance")
    #     params = dict(params)
    #     lowlim = params.get("lowlim", None)
    #     highlim = params.get("highlim", None)
    #     out_data = ManualTilt(lowlim=floatornone(lowlim), highlim=floatornone(highlim))
    #     return out_data

if __name__ == "__main__":  # pragma: no cover
    from Orange.widgets.utils.widgetpreview import WidgetPreview
    WidgetPreview(OWManualEditor).run(Orange.data.Table("iris.tab"))