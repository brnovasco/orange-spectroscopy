from sys import float_info

import numpy as np
import Orange.data
import pyqtgraph as pg
from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QSplitter, QWidget
from Orange.widgets import gui, settings
from Orange.widgets.settings import (DomainContextHandler, Setting,
                                     SettingProvider)
from Orange.widgets.utils.concurrent import ConcurrentWidgetMixin
from Orange.widgets.widget import Input, Msg, Output, OWBaseWidget, OWWidget
from orangecontrib.spectroscopy.preprocess import DegTilt
from orangecontrib.spectroscopy.util import getx
from orangecontrib.spectroscopy.widgets.owspectra import CurvePlot

class TiltLine(pg.InfiniteLine):
    def __init__(self, pos=pg.Point(0, 0), angle=0., pen=None, movable=False, bounds=None, hoverPen=None, label=None, labelOpts=None, span=..., markers=None, name=None):
        red = (255,0,0)#(128,128,128)
        pen = pg.mkPen(color=red, width=2, style=Qt.DashLine)
        super().__init__(pos, angle, pen, movable, bounds, hoverPen, label, labelOpts, span, markers, name)
    
    def setYPos(self, ynew):
        x, y = self.getPos()
        pos = pg.Point(x, ynew) 
        self.setPos(pos)

class SlopeControl:
    def __init__(self):
        self.val = 0.
        self.min = -90.
        self.max = 90.
        self.step = 1.

    def updateSlope(self, val):
        self.val = val

    def updateParams(self, **kwargs):
        self.min = kwargs.get('min')
        self.max = kwargs.get('max')
        self.step = kwargs.get('step')

    def _findSlopes(self, data):
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
        vslope = np.vectorize(slope)

        # skip the first column of the data and first element 
        # of the domain to avoid the infinity as dx == 0
        dx = x[1:] - xref
        dy = y[:,1:] - yref
        slopes = vslope(dx, dy)
        return slopes

    def initSlope(self, data: Orange.data.Table):
        """Calcullates the extrema of the slopes of the data in relation to a 
        reference point in the start value of the data with xref being the first value of the domain and 
        yref being the mean of all the first elements of the data arrays. 

        Args:
            data (Orange.data.Table): Standard Orange data table input.

        Returns:
            dictionary: Dictionary containing the coordinates of the reference point used and the slope 
            extrema, both as tuples.
        """
        y = data.X
        x = getx(data)
        xref = x[0]
        yref = np.mean(y[:,0])
        slopes = self._findSlopes(x, y, xref, yref)
        # updating
        self.min = np.min(slopes) 
        self.max = np.max(slopes)
        self.slope = np.mean([self.min, self.max]) 

    def updateSlopeRef(self, data: Orange.data.Table, yref):
        """Calcullates the extrema of the slopes of the data in relation to a 
        reference point in the start value of the data with xref being the first value of the domain and 
        yref being any value set by the user. 

        Args:
            data (Orange.data.Table): Standard Orange data table input.

        Returns:
            dictionary: Dictionary containing the coordinates of the reference point used and the slope 
            extrema, both as tuples.
        """
        y = data.X
        x = getx(data)
        xref = x[0]
        slopes = self._findSlopes(x, y, xref, yref)
        # updating
        self.min = np.min(slopes) 
        self.max = np.max(slopes)
        self.slope = np.mean([self.min, self.max]) 

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

    lowlim = Setting(None)
    highlim = Setting(None)

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
        gui.spin(slope_range, self.slope, "min", -90., 90., step=self.slope.step, label="Min", decimals=4,
                 callback=self.handleSlopeRangeSpin, spinType=float)
        gui.spin(slope_range, self.slope, "max", -90., 90., step=self.slope.step, label="Max", decimals=4,
                 callback=self.handleSlopeRangeSpin, spinType=float)
        
        # equation editor controls
        equation_box = gui.hBox(box, "Line Equation (y = x a + b)")
        self.shift = 0.
        gui.widgetLabel(equation_box, label="y = x ")
        gui.spin(equation_box, self.slope, "val", self.slope.min, self.slope.max, step=self.slope.step, label=None,
                callback=self.handleSlopeEquationSpin, spinType=float, callbackOnReturn=True, decimals=4)
        gui.label(equation_box, self, label=" +")
        gui.spin(equation_box, self, "shift", -float_info.max, float_info.max, step=0.001, label=None,
                 callback=self.handleShiftSlider, spinType=float)

        # setting plot control variables

        # data plot variables
        self.plot_in = CurvePlot(self)
        self.plot_out = CurvePlot(self)
        # auxiliary line plot in the same view of plot_in prepresenting the desired tilt angle and phase shift 
        # manually adjusted by the user
        self.tiltLine = TiltLine()
        self.plot_in.add_marking(self.tiltLine)
        # setting labels
        self.plot_in.label_title = "in_data"
        self.plot_out.label_title = "out_data"
        self.plot_in.labels_changed()
        self.plot_out.labels_changed()
        # padding 
        self.plot_in.plot.vb.x_padding = 0.1005   
        self.plot_out.plot.vb.y_padding = 0.1005 
        # setting plot views
        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Vertical)
        splitter.addWidget(self.plot_in)
        splitter.addWidget(self.plot_out)
        self.mainArea.layout().addWidget(splitter)

        gui.auto_commit(self.controlArea, self, "autocommit", "Send Data")
    
    @Inputs.data
    def set_data(self, data):
        self.data = data
        self.plot_in.set_data(data)
        self.slope.initSlope(self.data)
        # self.handleSlopeSlider() #TODO this shoudnt be here
    
    def _set_slope_params(self, params):
        if self.data is not None:
            self.slope_min, self.slope_max = params['slope']
            self.slope = np.sum(self.slope_min + self.slope_max )/2
            x0, y0 = params['refpos']
            self.linepos = pg.Point(x0, y0)
            self.shift = y0
            self.slope.step = .01 * (self.slope_max - self.slope_min)
            self.handleSlopeRangeSpin()

    def handleSlopeRangeSpin(self):
        # TODO: validate min < max
        # validate slope in range
        if self.slope < self.slope_min:
            self.slope = self.slope_min
        elif self.slope > self.slope_max:
            self.slope = self.slope_max
        print('Slope after update range {}'.format(self.slope))
        self.slope_slider.setValue(self.slope)
        self.slope_slider.setScale(minValue=self.slope_min, maxValue=self.slope_max, step=0.01*(self.slope_max-self.slope_min)/2)
        self.handleSlopeSlider()

    def _buttonSlope1Up(self):
        print("button increment +1")
        self._incrementSlope(1)

    def _buttonSlope10Up(self):
        print("button increment +1")
        self._incrementSlope(10)
    
    def _buttonSlope1Down(self):
        print("button increment -1")
        self._incrementSlope(-1)

    def _buttonSlope10Down(self):
        print("button increment -10")
        self._incrementSlope(-10)

    def _incrementSlope(self, ammount):
        self.slope += ammount*self.slope.step
        self.handleSlopeSlider()
    
    def _update_lines(self):
        self.plot_in.clear_markings() 
        self.plot_out.clear_markings()
        self.diagonal_line.setAngle(float(self.slope.val))
        self.diagonal_line.setPos(self.linepos)
        self.plot_in.add_marking(self.diagonal_line)
        self._reset_plot_in_viewrange()
    
    def _reset_plot_in_viewrange(self):
        if self.data is not None:
            datamax = np.max(self.data)
            datamin = np.min(self.data)
            yref = self.shift # linear coefficient of the line
            if yref < datamin:
                self.plot_in.range_y1 = yref
                self.plot_in.range_y2 = datamax
            elif yref > datamax:
                self.plot_in.range_y1 = datamin
                self.plot_in.range_y2 = yref
            self.plot_in.set_limits()

    def handleSlopeSlider(self):
        if self.data is not None:
            self._update_lines()
            self.commit.deferred()
        else:
            self.slope = 0.

    def handleShiftSlider(self):
        print(">>>> update_slope")
        if self.data is not None:
            xax_min = getx(self.data)[0]
            self.linepos = pg.Point(xax_min,-self.shift)             
            self._set_slope_params(update_slope_extrema(self.data, self.shift))
            self._update_lines()
            self.commit.deferred()
        
    @gui.deferred
    def commit(self):
        if self.data is not None:
            # this is where the out_data is calcullated
            out_data = DegTilt(slope=float(self.slope), shift=float(self.shift))(self.data)
            self.on_done(out_data)

    def on_done(self, out_data):
        self.plot_out.set_data(out_data) # set data to plot_out
        self.Outputs.data_edited.send(out_data) # send data to Output

    def handleNewSignals(self):
        print(">>>> on handleNewSignals")
        self.commit.now()

if __name__ == "__main__":  # pragma: no cover
    from Orange.widgets.utils.widgetpreview import WidgetPreview
    WidgetPreview(OWManualTilt).run(Orange.data.Table("iris.tab"))