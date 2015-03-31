from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.Processing import Processing
from processing.core.ProcessingLog import ProcessingLog
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from processing.parameters.ParameterBoolean import ParameterBoolean
from processing.parameters.ParameterCrs import ParameterCrs
from processing.parameters.ParameterExtent import ParameterExtent
from processing.parameters.ParameterMultipleInput import ParameterMultipleInput
from processing.parameters.ParameterNumber import ParameterNumber
from processing.parameters.ParameterRaster import ParameterRaster
from processing.parameters.ParameterSelection import ParameterSelection
from processing.parameters.ParameterString import ParameterString
from processing.parameters.ParameterTable import ParameterTable
from processing.parameters.ParameterVector import ParameterVector
from processing.parameters.ParameterFile import ParameterFile
from processing.outputs.OutputRaster import OutputRaster
from processing.outputs.OutputVector import OutputVector
from processing.outputs.OutputString import OutputString
from processing.outputs.OutputFactory import OutputFactory
from processing.tools import dataobjects
from QgsWPSClient.wpslib.wpsserver import WpsServer
from QgsWPSClient.wpslib.processdescription import ProcessDescription
from QgsWPSClient.wpslib.processdescription import getFileExtension,isMimeTypeVector,isMimeTypeRaster,isMimeTypeText,isMimeTypeFile
from QgsWPSClient.wpslib.processdescription import StringInput, TextInput, SelectionInput, VectorInput, MultipleVectorInput, RasterInput, MultipleRasterInput, FileInput, MultipleFileInput, ExtentInput, CrsInput, VectorOutput, RasterOutput, StringOutput
from QgsWPSClient.wpslib.executionrequest import ExecutionRequest
from QgsWPSClient.wpslib.executionrequest import createTmpGML
from QgsWPSClient.wpslib.executionresult import ExecutionResult
from PyQt4 import QtGui
from PyQt4.QtCore import *
from PyQt4.QtGui import qApp,QApplication,QMessageBox
import os

class WpsAlgorithm(GeoAlgorithm):

    def __init__(self, process, bookmark = False):
        self.process = process
        self.bookmark = bookmark
        GeoAlgorithm.__init__(self) #calls defineCharacteristics

    def defineCharacteristics(self):
        self.name = str(self.process.identifier)
        if self.bookmark:
            self.group = "Bookmarks"
        else:
            self.group = WpsAlgorithm.groupName(self.process.server)
        self.loadProcessDescription()
        self.buildParametersDialog()

    def getIcon(self):
        return QtGui.QIcon(os.path.dirname(__file__) + "/../images/wps.png")

    @staticmethod
    def groupName(server):
        return "WPS %s" % server.connectionName

    def loadProcessDescription(self):
        #retrieve and save if not saved before
        if not os.path.exists(self.process.processDescriptionFile(self.wpsDescriptionFolder())):
            self.getProcessDescription()
            if self.process.identifier == None or self.process.identifier == "":
                #Error reading description
                self.process.processXML = '' #Save empty description to prevent retry at next startup
            self.process.saveDescription(self.wpsDescriptionFolder())
        #load from file
        self.process.loadDescription(self.wpsDescriptionFolder())

    def wpsDescriptionFolder(self):
        from WpsAlgorithmProvider import WpsAlgorithmProvider
        return WpsAlgorithmProvider.WpsDescriptionFolder()

    def getProcessDescription(self):
        self.process.requestDescribeProcess()
        #Wait for answer
        while not self.process.loaded():
             qApp.processEvents()

    def buildParametersDialog(self):
        for input in self.process.inputs:
            inputType = type(input)
            if inputType == VectorInput:
                self.addParameter(ParameterVector(str(input.identifier), str(input.title), ParameterVector.VECTOR_TYPE_ANY, input.minOccurs == 0))
            elif inputType == MultipleVectorInput:
                self.addParameter(ParameterMultipleInput(str(input.identifier), str(input.title), ParameterVector.VECTOR_TYPE_ANY, input.minOccurs == 0))
            elif inputType == StringInput:
                self.addParameter(ParameterString(str(input.identifier), str(input.title)))
            elif inputType == TextInput:
                self.addParameter(ParameterString(str(input.identifier), str(input.title)))
            elif inputType == RasterInput:
                self.addParameter(ParameterRaster(str(input.identifier), str(input.title), input.minOccurs == 0))
            elif inputType == MultipleRasterInput:
                self.addParameter(ParameterMultipleInput(str(input.identifier), str(input.title), ParameterMultipleInput.TYPE_RASTER, input.minOccurs == 0))
            elif inputType == FileInput:
                #self.addParameter(ParameterFile(str(input.identifier), str(input.title), False, input.minOccurs == 0))
                self.addParameter(ParameterFile(str(input.identifier), str(input.title)))
            elif inputType == MultipleFileInput:
                pass #Not supported
            elif inputType == SelectionInput:
                self.addParameter(ParameterSelection(str(input.identifier), str(input.title), input.valList))
            elif inputType == ExtentInput:
                self.addParameter(ParameterExtent(str(input.identifier), str(input.title)))
            elif inputType == CrsInput:
                self.addParameter(ParameterCrs(str(input.identifier), "Projection", None))

        for output in self.process.outputs:
            outputType = type(output)
            if outputType == VectorOutput:
                self.addOutput(OutputVector(str(output.identifier), str(output.title)))
            elif outputType == RasterOutput:
                self.addOutput(OutputRaster(str(output.identifier), str(output.title)))
            elif outputType == StringOutput:
                self.addOutput(OutputString(str(output.identifier), str(output.title)))

    def defineProcess(self):
        """Create the execute request"""
        request = ExecutionRequest(self.process)
        request.addExecuteRequestHeader()

        # inputs
        useSelected = False
        request.addDataInputsStart()
        for input in self.process.inputs:
            inputType = type(input)
            value = self.getParameterValue(input.identifier)
            if inputType == VectorInput:
                layer = dataobjects.getObjectFromUri(value, False)
                if layer is None:
                    raise Exception("Couldn't extract layer for parameter '%s' from '%s'" % (input.identifier, value))
                mimeType = input.dataFormat["MimeType"]
                data = createTmpGML(layer, useSelected, mimeType)
                request.addGeometryInput(input.identifier, mimeType, input.dataFormat["Schema"], input.dataFormat["Encoding"], data, useSelected)
            elif inputType == MultipleVectorInput:
                #ParameterMultipleInput(input.identifier, input.title, ParameterVector.VECTOR_TYPE_ANY, input.minOccurs == 0))
                pass
            elif inputType == StringInput:
                request.addLiteralDataInput(input.identifier, str(value))
            elif inputType == TextInput:
                request.addLiteralDataInput(input.identifier, str(value))
            elif inputType == RasterInput:
                layer = dataobjects.getObjectFromUri(value, False)
                mimeType = input.dataFormat["MimeType"]
                request.addGeometryBase64Input(input.identifier, mimeType, layer)
            elif inputType == MultipleRasterInput:
                #ParameterMultipleInput(input.identifier, input.title, ParameterVector.TYPE_RASTER, input.minOccurs == 0))
                pass
            elif inputType == FileInput:
                mimeType = input.dataFormat["MimeType"]
                request.addFileBase64Input(input.identifier, mimeType, value)
            elif inputType == SelectionInput:
                #Value is dropdown index
                param = self.getParameterFromName(input.identifier)
                strval = str(param.options[int(value)])
                request.addLiteralDataInput(input.identifier, strval)
            elif inputType == ExtentInput:
                #ParameterExtent("EXTENT","EXTENT"))
                pass
            elif inputType == CrsInput:
                #ParameterCrs("CRS", "CRS"))
                pass
        #TODO: "selcetion only" checkbox
        request.addDataInputsEnd()

        # outputs
        request.addResponseFormStart()
        for output in self.process.outputs:
            outputType = type(output)
            if outputType == StringOutput:
                request.addLiteralDataOutput(output.identifier)
            elif outputType == VectorOutput or outputType == RasterOutput:
                mimeType = output.dataFormat["MimeType"]
                schema = output.dataFormat["Schema"]
                encoding = output.dataFormat["Encoding"]
                request.addReferenceOutput(output.identifier, mimeType, schema, encoding)
        request.addResponseFormEnd()

        request.addExecuteRequestEnd()
        return request.request

    def processAlgorithm(self, progress):
        postString = self.defineProcess()
        qDebug(postString)
        self.wps = ExecutionResult(self.getLiteralResult, self.getResultFile, self.errorResult, None)
        self.wps.executeProcess(self.process.processUrl, postString)
        #Wait for answer
        while not self.wps.finished():
             qApp.processEvents()

    def getLiteralResult(self, identifier, literalText):
        self.setOutputValue(identifier, literalText)
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, identifier + ": " + literalText)

    def getResultFile(self, identifier, mimeType, encoding, schema,  reply):
        # Get a unique temporary file name
        myQTempFile = QTemporaryFile()
        myQTempFile.open()
        ext = getFileExtension(mimeType)
        tmpFile = unicode(myQTempFile.fileName() + ext,'latin1')
        myQTempFile.close()

        # Write the data to the temporary file
        outFile = QFile(tmpFile)
        outFile.open(QIODevice.WriteOnly)
        outFile.write(reply.readAll())
        outFile.close()

        resultFile = self.wps.handleEncoded(tmpFile, mimeType, encoding,  schema)

        # Finally, load the data
        self.loadData(resultFile, mimeType, identifier)

    def loadData(self, resultFile, mimeType, identifier):
        # Vector data 
        # TODO: Check for schema GML and KML
        if isMimeTypeVector(mimeType) != None:
            self.setOutputValue(identifier, resultFile)
       # Raster data
        elif isMimeTypeRaster(mimeType) != None:
            self.setOutputValue(identifier, resultFile)

        # Text data
        elif isMimeTypeText(mimeType) != None:
            text = open(resultFile, 'r').read()
            self.setOutputValue(identifier, text)

        # Everything else
        elif isMimeTypeFile(mimeType) != None:
            text = open(resultFile, 'r').read()
            self.setOutputValue(identifier, text)

        # Everything else
        else:
            # For unsupported mime types we assume text
            content = open(resultFile, 'r').read()
            # TODO: This should have a safe option
            QMessageBox.information(None, QCoreApplication.translate("QgsWps", 'Process result (unsupported mime type)'), content)

    def errorResult(self, exceptionHtml):
        QMessageBox.critical(None, "Exception report", exceptionHtml)
        #ProcessingLog.addToLog(ProcessingLog.LOG_ERROR, exceptionHtml)
        #raise GeoAlgorithmExecutionException("Exception report\n" + exceptionHtml)
