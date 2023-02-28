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
from orangecontrib.spectroscopy.preprocess import DegTilt, Cut,  ManualTilt



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
        # slope controls (in degrees)
        self.slope = 0.
        self.slope_max = 90. # 90
        self.slope_min = -90. # -90

        box = gui.widgetBox(self.controlArea, "Map grid")

        slope_spins = gui.hBox(box)

        self.slope_step = .0001
        # gui.lineEdit(box, self, "slope_step",  label="Slope step size", valueType=float)
        gui.spin(slope_spins, self, "slope_step", -sys.float_info.max, sys.float_info.max, step=.0001, label="Slope Step",
                 callback=self._update_slope, spinType=float)
        
        gui.spin(slope_spins, self, "slope", self.slope_min, self.slope_max, step=self.slope_step, label="Slope",
                 callback=self._update_slope, spinType=float)

        gui.hSlider(box, self, "slope", 0., minValue=self.slope_min, maxValue=self.slope_max, step=self.slope_step, label="Slope slider", 
                    callback=self._update_slope, intOnly=False, labelFormat=" %.4f", createLabel=False)
        
        buttons = gui.hBox(box)
        gui.button(buttons, self, "-10x", callback=self._buttonSlopeDDown)
        gui.button(buttons, self, "-1x", callback=self._buttonSlopeDown)
        gui.button(buttons, self, "+1x", callback=self._buttonSlopeUp)
        gui.button(buttons, self, "+10x", callback=self._buttonSlopeUUp)

        # shift in radians
        self.shift = 0.
        
        gui.spin(box, self, "shift", -sys.float_info.max, sys.float_info.max, step=0.0001, label="Shift Spin",
                 callback=self._update_shift, spinType=float)

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Vertical)

        self.plot_in = CurvePlot(self)
        self.plot_out = CurvePlot(self)
        self.plot_in.plot.vb.x_padding = 0.1005  # pad view so that lines are not hidden
        self.plot_out.plot.vb.y_padding = 0.1005  # pad view so that lines are not hidden

        splitter.addWidget(self.plot_in)
        splitter.addWidget(self.plot_out)

        self.mainArea.layout().addWidget(splitter)

        self.linepos = pg.Point(0,0) 
        red = (255,0,0)#(128,128,128)
        pen = pg.mkPen(color=red, width=2, style=Qt.DashLine)
        self.diagonalLine = pg.InfiniteLine(pos=self.linepos, angle=float(self.slope), pen=pen, hoverPen=None, movable=False, span=(0, 2))
        self.plot_in.add_marking(self.diagonalLine)

        self.user_changed = False

        gui.auto_commit(self.controlArea, self, "autocommit", "Send Data")
        self._update_slope()

    @Inputs.data
    def set_data(self, data):
        print(">>>> on set_data (Input)")
        self.data = data
        self.plot_in.set_data(data)
        self.set_slope_limits()
        self._update_slope()

    def set_slope_limits(self):
        print(">>>> setting slope limits according to data")
        # pass # more complicated than that
        # set the shift to the mean of the data and the slope to the maximum value of the data
        if self.data is not None:
            x_ax = getx(self.data)
            delta_x = x_ax[-1] - x_ax[0]
            delta_data = np.max(self.data.X)-np.min(self.data.X)
            self.slope = np.degrees(np.arctan(delta_data/delta_x))
            self.shift = -np.mean(self.data.X)
            self.slope_step = .01 * self.slope

            print(">>>> print data mean {} data max {}, x: ({},{})".format(np.mean(self.data.X), np.max(self.data.X), x_ax[-1], x_ax[0]))
        else:
            self.slope = 0.

    def _buttonSlopeUp(self):
        self._incrementSlope(1)

    def _buttonSlopeUUp(self):
        self._incrementSlope(10)
    
    def _buttonSlopeDown(self):
        self._incrementSlope(-1)

    def _buttonSlopeDDown(self):
        self._incrementSlope(-10)

    def _incrementSlope(self, ammount):
        self.slope += ammount*self.slope_step
        self._update_slope()
    
    def _update_lines(self):
        print(">>>> updating lines", float(self.slope))
        self.plot_in.clear_markings() 
        self.plot_out.clear_markings()
        self.plot_in.add_marking(self.diagonalLine)
        self.diagonalLine.setAngle(float(self.slope))
        self.diagonalLine.setPos(self.linepos)

    def _update_slope(self):
        print(">>>> update_slope")
        if self.data is not None:
            self._update_lines()
            self.commit.deferred()
        else:
            self.slope = 0.

    def _update_shift(self):
        print(">>>> update_slope")
        if self.data is not None:
            xax_min = getx(self.data)[0]
            self.linepos = pg.Point(xax_min,self.shift) 
            self._update_lines()
            self.commit.deferred()
            print(self.shift)
        

    @gui.deferred
    def commit(self):
        print(">>>> on commit")
        if self.data is not None:
            # calculate out_data
            out_data = DegTilt(slope=float(self.slope), shift=float(self.shift))(self.data)
            self.on_done(out_data)

    def on_done(self, out_data):
        print(">>>> on_done")
        self.plot_out.set_data(out_data) # set data to plot_out
        self.Outputs.data_edited.send(out_data) # send data to Output

    def handleNewSignals(self):
        print(">>>> on handleNewSignals")
        self._update_slope()

if __name__ == "__main__":  # pragma: no cover
    from Orange.widgets.utils.widgetpreview import WidgetPreview
    WidgetPreview(OWManualEditor).run(Orange.data.Table("iris.tab"))