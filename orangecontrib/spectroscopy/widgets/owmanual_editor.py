import numpy as np
import Orange.data

from AnyQt.QtCore import Qt, QRectF, QPointF, QSize
from AnyQt.QtTest import QTest
from AnyQt.QtWidgets import QWidget, QPushButton, QGridLayout, QFormLayout, QAction, QVBoxLayout, QWidgetAction, QSplitter, QToolTip, QGraphicsRectItem

from Orange.data import Domain
from Orange.widgets import gui, settings
from Orange.widgets.widget import OWWidget, Input, Output, OWBaseWidget, Msg
from Orange.widgets.settings import Setting, ContextSetting, DomainContextHandler, SettingProvider
from Orange.widgets.utils.concurrent import TaskState, ConcurrentWidgetMixin, ConcurrentMixin
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

        self.lowlim = 0.
        self.highlim = 1.

        box = gui.widgetBox(self.controlArea, "Map grid")

        form = QWidget()
        formlayout = QFormLayout()
        form.setLayout(formlayout)
        box.layout().addWidget(form)

        self._lowlim_le = lineEditFloatRange(box, self, "lowlim", callback=self.commit)
        formlayout.addRow("Low Limit", self._lowlim_le)
        self._highlim_le = lineEditFloatRange(box, self, "highlim", callback=self.commit)
        formlayout.addRow("High Limit", self._highlim_le)

        self._lowlim_le.focusIn.connect(self.activateOptions)
        self._highlim_le.focusIn.connect(self.activateOptions)
        self.focusIn = self.activateOptions

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Vertical)

        self.plot_in = CurvePlot(self)
        self.plot_out = CurvePlot(self)
        self.plot_in.plot.vb.x_padding = 0.1005  # pad view so that lines are not hidden
        self.plot_out.plot.vb.y_padding = 0.1005  # pad view so that lines are not hidden

        splitter.addWidget(self.plot_in)
        splitter.addWidget(self.plot_out)

        self.mainArea.layout().addWidget(splitter)

        # self.line1 = MovableHline(position=self.lowlim, label="", report=self.plot_in)
        # self.line1.sigMoved.connect(lambda v: setattr(self, "lowlim", v))
        self.line2 = MovableHline(position=self.highlim, label="", report=self.plot_in)
        self.line2.sigMoved.connect(lambda v: setattr(self, "highlim", v))
        # for line in [self.line1, self.line2]:
        #     self.plot_in.add_marking(line)
            # line.hide()
        self.plot_in.add_marking(self.line2)

        self.data = None
        self.user_changed = False
        self.plot_out.show()

        gui.auto_commit(self.controlArea, self, "autocommit", "Send Data")
        self._change_input()

    def _change_input(self):
        self.commit.deferred()

    def activateOptions(self):
        self.plot_in.clear_markings() 
        self.plot_out.clear_markings()
        # for line in [self.line1, self.line2]:
        #     line.report = self.plot_in
        #     self.plot_in.add_marking(line)
        self.line2.report = self.plot_in
        self.plot_in.add_marking(self.line2)

    @Inputs.data
    def set_data(self, data):
        self.data = data
        self.plot_in.set_data(data)
    
    # def limits_etited_le(self, params):
    #     if params: #parameters were manually set somewhere else
    #         self.user_changed = True
    #     self.lowlim = params.get("lowlim", 0.)
    #     self.highlim = params.get("highlim", 1.)

    def setParameters(self, params):
        print("setParameters")
        if params: #parameters were manually set somewhere else
            self.user_changed = True
        self.lowlim = params.get("lowlim", 0.)
        self.highlim = params.get("highlim", 1.)
    
    # def on_done(self, data_edited):
    #     print("on_done")
    #     self.Outputs.data_edited.send(data_edited)

    @gui.deferred
    def commit(self):
        print("commit", self.lowlim, self.highlim)
        if self.data is None:
            return
        out_data = ManualTilt(lowlim=floatornone(self.lowlim), highlim=floatornone(self.highlim))(self.data)
        self.plot_out.set_data(out_data)
        self.Outputs.data_edited.send(out_data)

    def handleNewSignals(self):
        self.commit.deferred()

    # def _calc_manual_tilt(self):
    #     print("calc manual tilt")
    #     xax = getx(self.data)
    #     print("getx", xax)
    #     sloperad = (self.highlim - self.lowlim) / (xax[-1] - xax[0])
    #     # creating a line that passes through y = 0 and slope = self.ammount 
    #     inclined_curve = (xax - xax[0]) * np.tan(sloperad) # (not ideal) should calcullate slope in the frontend so user can see it as the line moves and then pass it as argument np.tan(np.deg2rad(self.ammount))
    #     new_X =  self.data.X - inclined_curve
    #     print("domain problems ", self.data.domain.attributes)
    #     atts = [a.copy(compute_value=SelectColumn(i, new_X))
    #             for i, a in enumerate(self.data.domain.attributes)]
    #     print("atts", atts)    
    #     # domain = Orange.data.Domain(atts, self.data.domain.class_vars,
    #     #                             self.data.domain.metas)
    #     # return self.data.from_table(domain, self.data)

    # @staticmethod
    # def createinstance(params):
    #     print("createinstance")
    #     params = dict(params)
    #     lowlim = params.get("lowlim", None)
    #     highlim = params.get("highlim", None)
    #     out_data = ManualTilt(lowlim=floatornone(lowlim), highlim=floatornone(highlim))
    #     return out_data

    # def set_preview_data(self, data):
    #     self.Warning.out_of_range.clear()
    #     x = getx(data)
    #     if len(x):
    #         minx = np.min(x)
    #         maxx = np.max(x)
    #         range = maxx - minx

    #         init_lowlim = round_virtual_pixels(minx + 0.1 * range, range)
    #         init_highlim = round_virtual_pixels(maxx - 0.1 * range, range)

    #         self._lowlime.set_default(init_lowlim)
    #         self._highlime.set_default(init_highlim)

    #         if not self.user_changed:
    #             self.lowlim = init_lowlim
    #             self.highlim = init_highlim
    #             self.edited.emit()

    #         if (self.lowlim < minx and self.highlim < minx) \
    #                 or (self.lowlim > maxx and self.highlim > maxx):
    #             self.parent_widget.Warning.preprocessor()
    #             self.Warning.out_of_range()

if __name__ == "__main__":  # pragma: no cover
    from Orange.widgets.utils.widgetpreview import WidgetPreview
    WidgetPreview(OWManualEditor).run(Orange.data.Table("iris.tab"))