import numpy as np
import pyqtgraph as pg
import colorcet

import Orange.data
from Orange.widgets.visualize.utils.plotutils import PlotItem, GraphicsView
from Orange.widgets.widget import OWWidget, Msg, Input, Output
from Orange.widgets import gui, settings

from AnyQt.QtCore import QRectF, Qt

from orangecontrib.spectroscopy.data import getx
from orangecontrib.spectroscopy.widgets.owhyper import ImageColorLegend
from orangecontrib.spectroscopy.widgets.owspectra import InteractiveViewBox


# put calculation widgets outside the class for easier reuse without the Orange framework or scripting
def sort_data(data):
    wn = getx(data)
    wn_sorting = np.argsort(wn)
    d = data[:, wn_sorting]
    return d

def calc_cos(table1, table2):

    ## TODO make selection in panel for dynamic (subtract mean) / static
    table1 = sort_data(table1)
    table2 = sort_data(table2)

    series1 = table1.X - table1.X.mean()
    series2 = table2.X - table2.X.mean()

    sync = series1.T @ series2 / (len(series1) - 1)

    # Hilbert-Noda transformation matrix
    HN = np.zeros((len(series1),len(series1)))
    for i in range(len(series1)):
        for j in range(len(series1)):
            if i != j:
                HN[i,j] = 1 / np.pi / (j-i)

    # asynchronous correlation
    asyn = series1.T @ HN @ series2 / (len(series1) - 1)

    return sync, asyn, series1, series2, getx(table1), getx(table2)
    # TODO handle non continuous data (after cut widget)

class COS2DViewBox(InteractiveViewBox):
    def autoRange2(self):
        if self is not self.graph.COS2Dplot.vb:
            super().autoRange()
            self.graph.COS2Dplot.vb.autoRange()
        else:
            super().autoRange()

    def suggestPadding(self, axis):
        return 0


class OWCos(OWWidget):
    # Widget's name as displayed in the canvas
    name = "2D Correlation Plot"

    # Short widget description
    description = (
        "Perform 2D correlation analysis with series spectra")

    # TODO needs icon
    icon = "icons/average.svg"

    # Define inputs and outputs
    class Inputs:
        data1 = Input("Data 1", Orange.data.Table, default=True)
        data2 = Input("Data 2", Orange.data.Table, default=True)

    class Outputs:
        # TODO implement outputting the matrix
        output = Output("2D correlation matrix", Orange.data.Table, default=True)

    settingsHandler = settings.DomainContextHandler()
    selector = settings.Setting(0)

    # autocommit = settings.Setting(True)

    want_main_area = True
    resizing_enabled = True

    class Warning(OWWidget.Warning):
        nodata = Msg("No useful data on input!")

    def __init__(self):
        super().__init__()

        self.data1 = None
        self.set_data1(self.data1)

        self.data2 = None
        self.set_data2(self.data2)

        #control area
        box = gui.widgetBox(self.controlArea, "Settings")

        gui.radioButtons(box, self, "selector", label="Plot type", btnLabels=("Synchronous", "Asynchronous"), box=box,
                         callback=self.plotCOS)
        gui.rubber(box)

        # plotting
        self.plotview = GraphicsView()
        ci = pg.GraphicsLayout()

        self.plotview.setCentralItem(ci)

        ci.layout.setColumnStretchFactor(0, 1)
        ci.layout.setRowStretchFactor(0, 1)
        ci.layout.setColumnStretchFactor(1, 5)
        ci.layout.setRowStretchFactor(1, 5)

        self.COS2Dplot = PlotItem(viewBox=COS2DViewBox(self))
        self.COS2Dplot.buttonsHidden = True
        ci.addItem(self.COS2Dplot, row=1, col=1)
        self.COS2Dplot.getAxis("left").setStyle(showValues=False)
        self.COS2Dplot.showAxis("top")
        self.COS2Dplot.showAxis("right")
        self.COS2Dplot.getAxis("top").setStyle(showValues=False)
        self.COS2Dplot.getAxis("right").setStyle(showValues=False)
        self.COS2Dplot.getAxis("bottom").setStyle(showValues=False)
        self.COS2Dplot.vb.border = 1
        self.COS2Dplot.vb.setAspectLocked(lock=True, ratio=1)
        self.COS2Dplot.vb.setMouseMode(pg.ViewBox.RectMode)

        # top spectrum plot
        self.top_plot = PlotItem(viewBox=COS2DViewBox(self))
        ci.addItem(self.top_plot, row=0, col=1)
        # visual settings
        self.top_plot.showAxis("right")
        self.top_plot.showAxis("top")
        self.top_plot.getAxis("left").setStyle(showValues=False)
        self.top_plot.getAxis("right").setStyle(showValues=False)
        self.top_plot.getAxis("bottom").setStyle(showValues=False)
        # interactive behavior settings
        self.top_plot.vb.setMouseEnabled(x=True, y=False)
        self.top_plot.enableAutoRange(axis='x')
        self.top_plot.setAutoVisible(x=True)
        self.top_plot.buttonsHidden = True
        self.top_plot.setXLink(self.COS2Dplot)
        # self.top_plot.vb.setMouseMode(pg.ViewBox.RectMode)
        # self.top_plot.vb.enableAutoRange(axis=pg.ViewBox.YAxis)

        # left spectrum plot
        self.left_plot = PlotItem(viewBox=COS2DViewBox(self))
        ci.addItem(self.left_plot, row=1, col=0)
        # visual settings
        self.left_plot.showAxis("right")
        self.left_plot.showAxis("top")
        self.left_plot.getAxis("right").setStyle(showValues=False)
        self.left_plot.getAxis("top").setStyle(showValues=False)
        self.left_plot.getAxis("bottom").setStyle(showValues=False)
        # interactive behavior settings
        self.left_plot.vb.setMouseEnabled(x=False, y=True)
        self.left_plot.enableAutoRange(axis='y')
        self.left_plot.setAutoVisible(y=True)
        self.left_plot.buttonsHidden = True
        self.left_plot.setYLink(self.COS2Dplot)
        self.left_plot.getViewBox().invertX(True)

        self.cbarCOS = ImageColorLegend()
        ci.layout.addItem(self.cbarCOS, 1, 3, 1, 1, alignment=Qt.AlignLeft)

        self.mainArea.layout().addWidget(self.plotview)

        # gui.auto_commit(self.controlArea, self, "autocommit", "Apply")
    # TODO subclass ViewBox for the 2D and spectral plots so that zooming is better
    # TODO - implement the aspect ratio lock for the 2D plot
        # initialize the widget with the right aspect ratio so that the pixel is square
        # keep the pixels always square, especially when changing the widget size
    # TODO - change the "0" label on left_plot to white so that the axes line up but it is invisible
    # TODO - the zooming behaves weirdly: when the zoom display stops it still zooms in the BG and the user needs to
        #  scroll back a lot to unzoom
    # TODO - zooming would be better with no scrolling but rather selecting a range on top or lef or a square on 2D plot
    # TODO - implement cross-hair like it is on Spectra but showing the same positions between the three plots
    # [x] TODO - make sure that the orientation of the left/top spectra correspond to the matrix!
    # TODO - implement rescale Y after zoom

    @Inputs.data1
    def set_data1(self, dataset):
        self.data1 = dataset

    @Inputs.data2
    def set_data2(self, dataset):
        self.data2 = dataset

    def handleNewSignals(self):

        if self.data1 is not None:
            if self.data2 is None:
                self.data2 = self.data1

            self.cosmat = calc_cos(self.data1, self.data2)

        self.commit()

    def plot_type_change(self):
        self.commit()

    def plotCOS(self):
        cosmat = self.cosmat[self.selector]
        topSP = self.cosmat[2]
        leftSP = self.cosmat[3]
        topSPwn = self.cosmat[4]
        leftSPwn = self.cosmat[5]

        p = pg.mkPen('r', width=3)
        self.COS2Dplot.clear()

        COSimage = pg.ImageItem(image=cosmat)
        COSimage.setLevels([-1 * np.absolute(cosmat).max(), np.absolute(cosmat).max()])
        COSimage.setLookupTable(np.array(colorcet.diverging_bwr_40_95_c42) * 255)
        COSimage.setOpts(axisOrder='row-major')
        COSimage.setRect(QRectF(leftSPwn.min(),
                                leftSPwn.min(),
                                (leftSPwn.max() - leftSPwn.min()),
                                (leftSPwn.max() - leftSPwn.min())))

        self.COS2Dplot.addItem(COSimage)


        self.cbarCOS.set_range(-1 * np.absolute(cosmat).max(), np.absolute(cosmat).max())
        self.cbarCOS.set_colors(np.array(colorcet.diverging_bwr_40_95_c42) * 255)

        self.left_plot.plot(leftSP.mean(axis=0), leftSPwn, pen=p)

        self.top_plot.plot(topSPwn, topSP.mean(axis=0), pen=p)

    def commit(self):
            self.plotCOS()

if __name__ == "__main__":  # pragma: no cover
    from Orange.widgets.utils.widgetpreview import WidgetPreview
    # WidgetPreview(OWCos).run(set_data1=Orange.data.Table("collagen"), set_data2=None)
    # WidgetPreview(OWCos).run(set_data1=Orange.data.Table("collagen"), set_data2=Orange.data.Table("collagen"))
    t = 'rand'
    if t=='normal':
        print('reading normal')
        WidgetPreview(OWCos).run(set_data1=Orange.data.Table("/Users/borondics/2dcos-test.dat"),
                                 set_data2=Orange.data.Table("/Users/borondics/2dcos-test.dat"))
    elif t=='updown':
        print('reading up-down')
        WidgetPreview(OWCos).run(set_data1=Orange.data.Table("/Users/borondics/2dcos-test-ud.dat"),
                                 set_data2=Orange.data.Table("/Users/borondics/2dcos-test-ud.dat"))
    elif t=='rand':
        print('reading randomized')
        WidgetPreview(OWCos).run(set_data1=Orange.data.Table("/Users/borondics/2dcos-test-rand.dat"),
                                 set_data2=Orange.data.Table("/Users/borondics/2dcos-test-rand.dat"))

