from sys import float_info

import numpy as np
import Orange.data
import pyqtgraph as pg
from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QSplitter, QWidget
from Orange.widgets import gui, settings
from Orange.widgets.settings import (DomainContextHandler, SettingProvider)
from Orange.widgets.utils.concurrent import ConcurrentWidgetMixin
from Orange.widgets.widget import Input, Msg, Output, OWBaseWidget, OWWidget
from orangecontrib.spectroscopy.preprocess import DegTilt
from orangecontrib.spectroscopy.util import getx
from orangecontrib.spectroscopy.widgets.owspectra import CurvePlot

class TiltLine(pg.InfiniteLine):
    def __init__(self, pos=pg.Point(0, 0), angle=0., pen=None, movable=True, bounds=None, hoverPen=None, label=None, labelOpts=None, span=(0,1), markers=None, name=None):
        red = (255,0,0)#(128,128,128)
        pen = pg.mkPen(color=red, width=2, style=Qt.DashLine)
        super().__init__(pos, angle, pen, movable, bounds, hoverPen, label, labelOpts, span, markers, name)

    def update_params(self, slope, xpos, ypos):
        pos = pg.Point(float(xpos), float(ypos)) 
        self.setPos(pos)
        self.setAngle(float(slope))

class SlopeControl(OWWidget):
    """ SlopeControl: defines an object wit useful information for the slope parameters handling and slope calcullation.
    """
    def __init__(self):
        super().__init__()
        self.setDefault()

    def setDefault(self):
        self.val = 0.
        self.min = -90.
        self.max = 90.
        self.step = 1.
        self.xref = 0.
        self.yref = 0.
        self.x = None
        self.y = None

    def updateData(self, data: Orange.data.Table):
        self.y = data.X
        self.x = getx(data)
        self.xref = self.x[0]
        self.yref = np.mean(self.y[:,0])
        self.min, self.max, self.val = self._calcSlopes()
    
    def onReset(self):
        self.xref = self.x[0]
        self.yref = np.mean(self.y[:,0])
        self.min, self.max, self.val = self._calcSlopes()

    def onUpdateRef(self):
        # updating ref position doesn't change the previusly set self.val
        self.min, self.max, _ = self._calcSlopes()
    
    def onUpdateLims(self):
        # reset if entry is not valid
        if self.max < self.min:
            print("do I need this?")
            self.min, self.max = -90., 90.

    def onUpdateSlope(self):
        if self.val < self.min:
            self.min = self.val
        elif self.max < self.val:
            self.max = self.val

    def _calcSlopes(self):
        """Calculate the slopes in relation to a reference point (xref, yref).

        Args:
            x (array): 1D Array representing the x axis for the data. Cenerally from the data.domain property 
            y (array): 2D Array representing the data with each column related to an element of the domain
            xref (number): x coordinate of the reference point. Generally the first element of the x array.
            yref (numbert): y coordinate of the reference point. Can be any number but generally the mean of the
            first elements of the data arrays, or the mean of all elements of the first column of y.
        Returns
            slopes (array): 2D array representing the calcullated slopes with shape (y.shape[0]-1, y.shape[1]-1)
        """
        def slope(dx, dy):
            try:
                return np.degrees(np.arctan(dy/dx))
            except ZeroDivisionError as err:
                print('run-time error: {err}. Check for dx==0 when its not supposed to. dx value:{dx}'.format(err=err, dx=dx))
                raise
            except Exception as err:
                print(f"Unexpected {err=}, {type(err)=}")
                raise
        # vectorized form of the slope function
        vslope = np.vectorize(slope)
        # skip the first column of the data and first element 
        # of the domain to avoid the infinity as dx == 0
        dx = self.x[1:] - self.xref
        dy = self.y[:,1:] - self.yref
        slopes = vslope(dx, dy)
        min = np.min(slopes) 
        max = np.max(slopes)
        val = np.mean([min, max])
        return min, max, val         

class OWManualTilt(OWWidget, ConcurrentWidgetMixin):
    """OWManualTilt Widget with input controllers for adjusting manually the slope of a line of 
    reference that will be subtracted from the data. The user can vary its slope using a slider or 
    setting its value in degrees in  a numerical input form. He can also change the vertical shift, 
    in addition to editing the limits and step size of the slider controller.

    Attributes:
        Inputs (Orange.data.Table): Default OWWidget Input containing multiple spectra
    """

    name = "Manual Tilt"
    description = "Widget with input controllers for adjusting manually the slope of a line of " \
    "reference that will be subtracted from the data. The user can vary its slope using a slider or " \
    "setting its value in degrees in a numerical input form in addition to changing the vertical " \
    "shift of the line, and editing the limits and step size of the slider."

    class Inputs:
        data = Input("Data", Orange.data.Table, default=True)

    class Outputs:
        data_edited = Output("Edited Data", Orange.data.Table, default=True)

    icon = "icons/manualtilt.svg"
    priority = 200 # change this number to an appropriate one
    keywords = ["image", "spectral", "chemical", "imaging"]

    settings_version = 6
    settingsHandler = DomainContextHandler()

    plot_in = SettingProvider(CurvePlot)
    plot_out = SettingProvider(CurvePlot)

    autocommit = settings.Setting(True)

    class Warning(OWBaseWidget.Warning):
        out_of_range = Msg("Limits are out of range.")

    def __init__(self):
        super().__init__()
        ConcurrentWidgetMixin.__init__(self)

        # data control variable
        self.data = None

        # init slope control 
        self.slope = SlopeControl()

        # grid control variable for input controllers (slider, spin and buttons)
        box = gui.widgetBox(self.controlArea, "Map grid")    

        slope_controls = gui.vBox(box, "Slope Controls")
        self.slope_slider = gui.hSlider(slope_controls, self.slope, "val", 0., minValue=self.slope.min, maxValue=self.slope.max, step=self.slope.step, label="Slope", 
                    callback=self.handleSlopeSlider, intOnly=False, labelFormat="%0.4f", createLabel=False)
        
        # slope_buttons elements
        slope_buttons = gui.hBox(slope_controls)
        gui.button(slope_buttons, self, "-10x", callback=self._buttonSlope10Down, autoDefault=False)
        gui.button(slope_buttons, self, "-1x", callback=self._buttonSlope1Down, autoDefault=False)
        gui.button(slope_buttons, self, "+1x", callback=self._buttonSlope1Up, autoDefault=False)
        gui.button(slope_buttons, self, "+10x", callback=self._buttonSlope10Up, autoDefault=False)

        # slope_range edit elements
        slope_range = gui.hBox(slope_controls)
        gui.label(slope_range, self,"Slope Range")
        gui.spin(slope_range, self.slope, "min", minv=-90., maxv=self.slope.max, step=self.slope.step, label="Min", decimals=4,
                 callback=self.handleSlopeRangeSpin, spinType=float)
        gui.spin(slope_range, self.slope, "max", minv=self.slope.min, maxv=90., step=self.slope.step, label="Max", decimals=4,
                 callback=self.handleSlopeRangeSpin, spinType=float)
        
        # equation editor controls
        equation_box = gui.hBox(box, "Line Equation (y = x * a + b)")
        gui.widgetLabel(equation_box, label="y = x * ")
        gui.spin(equation_box, self.slope, "val", minv=-float_info.max, maxv=float_info.max, step=self.slope.step, label=None,
                callback=self.handleEquationSpinSlope, spinType=float, decimals=4, controlWidth=100)
        gui.label(equation_box, self, label=" +")
        gui.spin(equation_box, self.slope, "yref", minv=-float_info.max, maxv=float_info.max, step=0.0001, label=None,
                 callback=self.handleEquationSpinYref, spinType=float, decimals=4, controlWidth=100)
        gui.button(equation_box, self, "Reset", callback=self.handleResetSlope, autoDefault=False, width=100)

        # setting plot control variables

        # data plot variables
        self.plot_in = CurvePlot(self)
        self.plot_out = CurvePlot(self)
        # auxiliary line plot in the same view of plot_in prepresenting the desired tilt angle and phase shift 
        # manually adjusted by the user
        self.tilt_line = TiltLine()
        # setting plot view range
        self.in_data_lims = {'x': (0, 0), 'y': (0, 0)}
        # adjusting padding and plot info
        self._set_plot_view()
        # adding plots to splitter view
        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Vertical)
        splitter.addWidget(self.plot_in)
        splitter.addWidget(self.plot_out)
        self.mainArea.layout().addWidget(splitter)
        # setting auto commit after changes in the controls
        gui.auto_commit(self.controlArea, self, "autocommit", "Send Data")
    
    @Inputs.data
    def set_data(self, data):
        self.data = data
        if data is not None:
            self.slope.updateData(data)
            self._update_slider()
            self.plot_in.set_data(data)
            self._update_data_lims()
            self._update_plots()
            self.commit.deferred() 
        else:
            self.slope.setDefault() 
            self._update_slider()
            self.plot_in.set_data(data)
            self._update_plots()
            self.commit.deferred() 

    def _update_slider(self):
        self.slope_slider.setValue(self.slope.val)
        self.slope_slider.setScale(minValue=self.slope.min, maxValue=self.slope.max, step=self.slope.step)

    def _update_plots(self):
        # clear views
        self.plot_in.clear_markings() 
        # update tilt_line params
        self.tilt_line.update_params(self.slope.val, self.slope.xref, self.slope.yref)
        # adding tilt_line to view and update view
        self.plot_in.add_marking(self.tilt_line)
        self._update_data_lims()
        self._set_plot_view()

    def _set_plot_view(self):
        # setting labels
        self.plot_in.label_title = "in_data"
        self.plot_out.label_title = "out_data"
        # splitter
        self.plot_in.plot.vb.x_padding = 0.005  # pad view so that lines are not hidden
        self.plot_out.plot.vb.x_padding = 0.005  # pad view so that lines are not hidden
        self.plot_in.labels_changed()
        self.plot_out.labels_changed()

    def _update_data_lims(self):
        if self.data is not None:
            xmin, xmax = getx(self.data)[[0, -1]]
            ymin, ymax = np.min(self.data), np.max(self.data)
            # reference y coordinate (linear coefficient) from tilt_line that needs to be visible
            yref = self.slope.yref
            # checking y range
            if yref < ymin:
                ymin = yref
            elif ymax < yref:
                ymax = yref
            # resetting view
            self._reset_plot_in_viewrange(xlims=(xmin, xmax), ylims=(ymin, ymax))
    
    def _reset_plot_in_viewrange(self, xlims, ylims):
        # data limits
        xmin, xmax = xlims
        ymin, ymax = ylims
        # setting x range in plot_in
        self.plot_in.range_x1 = xmin
        self.plot_in.range_x2 = xmax
        # setting y range in plot_in
        self.plot_in.range_y1 = ymin
        self.plot_in.range_y2 = ymax
        # updating settings in component
        self.plot_in.set_limits()         

    def _buttonSlope1Up(self):
        print("button increment +1")
        self.handleSlopeChangeButtons(1)

    def _buttonSlope10Up(self):
        print("button increment +1")
        self.handleSlopeChangeButtons(10)
    
    def _buttonSlope1Down(self):
        print("button increment -1")
        self.handleSlopeChangeButtons(-1)

    def _buttonSlope10Down(self):
        print("button increment -10")
        self.handleSlopeChangeButtons(-10)

    def handleSlopeChangeButtons(self, ammount):
        if self.data is not None:
            self.slope.val += ammount*self.slope.step
            self._update_slider()
            self._update_plots()
            self.commit.deferred()

    def handleSlopeSlider(self):
        if self.data is not None:
            self.slope.onUpdateSlope()
            self._update_plots()
            self.commit.deferred()

    def handleEquationSpinSlope(self):
        if self.data is not None:
            self.slope.onUpdateSlope()
            self._update_slider()
            self._update_plots()
            self.commit.deferred()
    
    def handleEquationSpinYref(self):
        if self.data is not None:
            self.slope.onUpdateRef()
            self._update_data_lims()
            self._update_plots()
            self.commit.deferred()

    def handleSlopeRangeSpin(self):
        self.slope.onUpdateLims()
        self._update_slider()

    def handleResetSlope(self):
        self.slope.onReset()
        self._update_slider()
        self._update_data_lims()
        self._update_plots()
        self.commit.deferred() 

    @gui.deferred
    def commit(self):
        if self.data is not None:
            # this is where the out_data is calcullated
            out_data = DegTilt(slope=float(self.slope.val), shift=float(self.slope.yref))(self.data)
            self.on_done(out_data)

    def on_done(self, out_data):
        self.plot_out.set_data(out_data) # set data to plot_out
        self.Outputs.data_edited.send(out_data) # send data to Output

if __name__ == "__main__":  # pragma: no cover
    from Orange.widgets.utils.widgetpreview import WidgetPreview
    WidgetPreview(OWManualTilt).run(Orange.data.Table("iris.tab"))