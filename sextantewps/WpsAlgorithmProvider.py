from sextante.core.AlgorithmProvider import AlgorithmProvider
from sextante.core.SextanteConfig import Setting, SextanteConfig
from sextante.core.SextanteUtils import mkdir, SextanteUtils
from WpsAlgorithm import WpsAlgorithm
from AddNewWpsAction import AddNewWpsAction
from WpsServerAction import WpsServerAction
from QgsWPSClient.wpslib.wpsserver import WpsServer
from QgsWPSClient.wpslib.processdescription import ProcessDescription
import os
from PyQt4 import QtGui

class WpsAlgorithmProvider(AlgorithmProvider):

    WPS_DESCRIPTIONS = "WPS_DESCRIPTIONS"

    def __init__(self, wpsDockWidget):
        AlgorithmProvider.__init__(self)
        self.actions.append(AddNewWpsAction(wpsDockWidget))

    def initializeSettings(self):
        AlgorithmProvider.initializeSettings(self)
        SextanteConfig.addSetting(Setting(self.getDescription(),
                                          WpsAlgorithmProvider.WPS_DESCRIPTIONS,
                                          "WPS description cache folder",
                                          WpsAlgorithmProvider.WpsDescriptionFolder()))

    @staticmethod
    def WpsDescriptionFolder():
        folder = SextanteConfig.getSetting(WpsAlgorithmProvider.WPS_DESCRIPTIONS)
        if folder == None:
            folder = unicode(os.path.join(SextanteUtils.userFolder(), "wps"))
        mkdir(folder)
        return os.path.abspath(folder)

    def unload(self):
        AlgorithmProvider.unload(self)
        SextanteConfig.removeSetting( WpsAlgorithmProvider.WPS_DESCRIPTIONS)

    def getName(self):
        return "wps"

    def getDescription(self):
        '''This is the name that will appear on the toolbox group.'''
        return "WPS"

    def getSupportedOutputVectorLayerExtensions(self):
        return ["gml"]

    def getSupportedOutputRasterLayerExtensions(self):
        return ["tif"]

    def getIcon(self):
        return QtGui.QIcon(os.path.dirname(__file__) + "/../images/wps.png")

    def _serversAlgsList(self):
        algs = []
        for server in WpsServer.getServers():
            action = next((a for a in self.actions if isinstance(a, WpsServerAction) and a.server.connectionName == server.connectionName), None)
            if action:
                algs += action.processalgs
            else:
                action = WpsServerAction(server)
                self.actions.append(action)
                dir = server.processDescriptionFolder(WpsAlgorithmProvider.WpsDescriptionFolder())
                if os.path.exists(dir):
                    #load from descriptions
                    for fn in os.listdir(dir):
                        process = ProcessDescription(server, fn)
                        action.processalgs.append(  WpsAlgorithm(process) )
                algs += action.processalgs
        return algs

    def _bookmarkAlgsList(self):
        bookmarkAlgs = []
        for process in ProcessDescription.getBookmarks():
            bookmarkAlgs.append( WpsAlgorithm(process, True) )
        return bookmarkAlgs

    def _loadAlgorithms(self):
        self.algs = self._serversAlgsList()
        self.algs += self._bookmarkAlgsList()
