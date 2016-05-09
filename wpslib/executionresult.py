# -*- coding: utf-8 -*-
"""
 /***************************************************************************
   QGIS Web Processing Service Plugin
  -------------------------------------------------------------------
 Date                 : 09 November 2009
 Copyright            : (C) 2009 by Dr. Horst Duester
 email                : horst dot duester at kappasys dot ch

  ***************************************************************************
  *                                                                         *
  *   This program is free software; you can redistribute it and/or modify  *
  *   it under the terms of the GNU General Public License as published by  *
  *   the Free Software Foundation; either version 2 of the License, or     *
  *   (at your option) any later version.                                   *
  *                                                                         *
  ***************************************************************************/
"""

from PyQt4.QtCore import *
from PyQt4.QtNetwork import *
from PyQt4.QtGui import QApplication,QMessageBox
from PyQt4 import QtXml
from PyQt4.QtXmlPatterns import QXmlQuery
from qgis.core import QgsNetworkAccessManager
from functools import partial
from QgsWPSClient.wpslib.processdescription import getFileExtension
import tempfile, base64, sys
import QgsWPSClient.apicompat


# Execute result example:
#
#<?xml version="1.0" encoding="utf-8"?>
#<wps:ExecuteResponse xmlns:wps="http://www.opengis.net/wps/1.0.0" xmlns:ows="http://www.opengis.net/ows/1.1" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/wps/1.0.0 http://schemas.opengis.net/wps/1.0.0/wpsExecute_response.xsd" service="WPS" version="1.0.0" xml:lang="eng" serviceInstance="http://www.kappasys.ch/pywps?service=WPS&amp;request=GetCapabilities&amp;version=1.0.0" statusLocation="http://www.kappasys.ch/pywps/wpsoutputs/pywps-136243739626.xml">
#    <wps:Process wps:processVersion="1.0">
#        <ows:Identifier>returner</ows:Identifier>
#        <ows:Title>Return process</ows:Title>
#        <ows:Abstract>This is demonstration process of PyWPS, returns the same file, it gets on input, as the output.</ows:Abstract>
#    </wps:Process>
#    <wps:Status creationTime="2013-03-04T23:49:56Z">
#        <wps:ProcessSucceeded>PyWPS Process returner successfully calculated</wps:ProcessSucceeded>
#    </wps:Status>
#    <wps:ProcessOutputs>
#        <wps:Output>
#            <ows:Identifier>output2</ows:Identifier>
#            <ows:Title>Output vector data</ows:Title>
#            <wps:Reference xlink:href="http://www.kappasys.ch/pywps/wpsoutputs/output2-30429" mimeType="text/xml"/>
#        </wps:Output>
#        <wps:Output>
#            <ows:Identifier>text</ows:Identifier>
#            <ows:Title>Output literal data</ows:Title>
#            <wps:Data>
#                <wps:LiteralData dataType="integer">33</wps:LiteralData>
#            </wps:Data>
#        </wps:Output>
#        <wps:Output>
#            <ows:Identifier>output1</ows:Identifier>
#            <ows:Title>Output vector data</ows:Title>
#            <wps:Reference xlink:href="http://www.kappasys.ch/pywps/wpsoutputs/output1-30429" mimeType="text/xml"/>
#        </wps:Output>
#    </wps:ProcessOutputs>
#</wps:ExecuteResponse>

def decodeBase64(infileName,  mimeType="", tmpDir=None):
    try:
        tmpFile = tempfile.NamedTemporaryFile(prefix="base64", suffix=getFileExtension(mimeType), dir=tmpDir, delete=False) 
        infile = open(infileName)
        outfile = open(tmpFile.name, 'w')
        base64.decode(infile,outfile)

        infile.close()
        outfile.close()
    except:
        raise

    return tmpFile.name

class ExecutionResult(QObject):
    """
    Send request XML and process result
    """
    
    fetchingResult = pyqtSignal(int)

    def __init__(self, literalResultCallback, resultFileCallback, successResultCallback, errorResultCallback, streamingHandler, progressBar=None, statusLabel=None):
        QObject.__init__(self)
        self._getLiteralResult = literalResultCallback
        self._resultFileCallback = resultFileCallback
        self._successResultCallback = successResultCallback
        self._errorResultCallback = errorResultCallback
        self._streamingHandler = streamingHandler
        self._processExecuted = False
        self.progressBar = progressBar
        self.statusLabel = statusLabel
        self.noFilesToFetch = 0

    def executeProcess(self, processUrl, requestXml):
        self._processExecuted = False
        self.noFilesToFetch = 0

        #postData = QByteArray()
        #postData.append(unicode(requestXml))
    
        scheme = processUrl.scheme()
        path = processUrl.path()
        server = processUrl.host()
        port = processUrl.port()
        
        processUrl.removeQueryItem('Request')
        processUrl.removeQueryItem('identifier')
        processUrl.removeQueryItem('Version')
        processUrl.removeQueryItem('Service')

        qDebug("Post URL=" + pystring(processUrl))
    
        thePostHttp = QgsNetworkAccessManager.instance()
        request = QNetworkRequest(processUrl)
        request.setHeader( QNetworkRequest.ContentTypeHeader, "text/xml; charset=utf-8" )
        #qDebug("Post REQUEST=" + pystring(postData))
        self.thePostReply = thePostHttp.post(request, requestXml.encode("utf-8"))
        self.thePostReply.finished.connect(partial(self.resultHandler, self.thePostReply) )
        

    def finished(self):
        return self._processExecuted and (self.noFilesToFetch == 0)

    def resultHandler(self, reply):
        """Handle the result of the WPS Execute request and add the outputs as new
           map layers to the registry or open an information window to show literal
           outputs."""
        resultXML = reply.readAll().data()
        reply.deleteLater()
        qDebug(resultXML)
        self.parseResult(resultXML)
        return True

    def parseResult(self, resultXML):
        self.doc = QtXml.QDomDocument()
        self.doc.setContent(resultXML,  True)

        resultNodeList = self.doc.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0","Output")

        # TODO: Check if the process does not run correctly before
        if resultNodeList.size() > 0:
            for i in range(resultNodeList.size()):
              f_element = resultNodeList.at(i).toElement()
              identifier = pystring(f_element.elementsByTagNameNS("http://www.opengis.net/ows/1.1","Identifier").at(0).toElement().text()).strip()

              # Fetch the referenced complex data
              if f_element.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0", "Reference").size() > 0:
                reference = f_element.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0","Reference").at(0).toElement()

                # Get the reference
                fileLink = reference.attribute("href", "0")
                
                # Try with namespace if not successful
                if fileLink == '0':
                  fileLink = reference.attributeNS("http://www.w3.org/1999/xlink", "href", "0")
                if fileLink == '0':
                  QMessageBox.warning(None, '', 
                      pystring(QApplication.translate("QgsWps", "WPS Error: Unable to download the result of reference: ")) + pystring(fileLink))
                  return False

                # Get the mime type of the result
                mimeType = pystring(reference.attribute("mimeType", "0")).lower()
                # Get the encoding of the result, it can be used decoding base64
                encoding = pystring(reference.attribute("encoding", "")).lower()
                schema = pystring(reference.attribute("schema", "")).lower()                
                
                if fileLink != '0':
                  if "playlist" in mimeType: # Streaming based process?
                    self._streamingHandler(encoding, fileLink)
                  else: # Conventional processes
                    self.fetchResult(encoding, schema,  fileLink, identifier,mimeType)

              elif f_element.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0", "ComplexData").size() > 0:
                complexData = f_element.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0","ComplexData").at(0).toElement()

                # Get the mime type of the result
                self.mimeType = pystring(complexData.attribute("mimeType", "0")).lower()

                # Get the encoding of the result, it can be used decoding base64
                encoding = pystring(complexData.attribute("encoding", "")).lower()
                try:
                  schema = pystring(reference.attribute("schema", "")).lower()                
                except:
                  pass

                if "playlist" in self.mimeType:
                  playlistUrl = f_element.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0", "ComplexData").at(0).toElement().text()
                  self._streamingHandler(encoding, playlistUrl)

                else: # Other ComplexData are not supported by this WPS client
                  QMessageBox.warning(None, '', 
                    pystring(QApplication.translate("QgsWps", "WPS Error: The mimeType '" + self.mimeType + "' is not supported by this client")))

              elif f_element.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0", "LiteralData").size() > 0:
                literalText = f_element.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0", "LiteralData").at(0).toElement().text()
                self._getLiteralResult(identifier, literalText)
              else:
                QMessageBox.warning(None, '', 
                  pystring(QApplication.translate("QgsWps", "WPS Error: Missing reference or literal data in response")))
            self._processExecuted = True
        else:
            resultNodeList = self.doc.elementsByTagNameNS("http://www.opengis.net/wps/1.0.0","ExecuteResponse")
            if resultNodeList.size() > 0:
                f_element = resultNodeList.at(0).toElement()
                fileUrl = f_element.attribute("statusLocation", "0")
                if fileUrl != "0":
                    self.myHttp = QgsNetworkAccessManager.instance()
                    url = QUrl()
                    url.setUrl(fileUrl)
                    self.thePostReply=self.myHttp.get(QNetworkRequest(url))
                    self.thePostReply.finished.connect(partial(self.resultHandler, self.thePostReply) )

            status = self.doc.elementsByTagName("Status")
            try:
                child = status.at(0).firstChildElement()
                if child.localName() == "ProcessSucceeded":
                    print >> sys.stderr,"ProcessSucceeded"
                    self._successResultCallback()
                else:
                    print >> sys.stderr,child.text()
                    if child.localName() == "ProcessAccepted":
                        self.showProgressBar(0,100,child.text())
                    else:
                        if child.localName() == "ProcessStarted":
                            v=child.attribute("percentCompleted","0")
                            self.showProgressBar(int(v),100,child.text())
                        else:
                            if child.localName() == "ProcessSucceeded":
                                QMessageBox.warning(None, '', 
                                    pystring(QApplication.translate("QgsWps", "WPS Error: Service ended but no result was found")))
                                return False
                            else:
                                self.errorHandler(child.text())
                    import time
                    time.sleep(1.6)
            except Exception,e:
                QMessageBox.warning(None, '', 
                    pystring(QApplication.translate("QgsWps", "WPS Error: ")+str(e)))
                return self.errorHandler(resultXML)

    def fetchResult(self, encoding, schema,  fileLink, identifier, mimeType):
        self.noFilesToFetch += 1
        print >> sys.stderr,"File to fetch "+str(self.noFilesToFetch)
        url = QUrl(fileLink)
        self.myHttp = QgsNetworkAccessManager.instance()
        self.theReply = self.myHttp.get(QNetworkRequest(url))
        self.fetchingResult.emit(self.noFilesToFetch)

        # Append encoding to 'finished' signal parameters
        self.encoding = encoding
        self.schema = schema
        self.theReply.finished.connect(partial(self.getResultFile, identifier, mimeType, encoding, schema,  self.theReply))
        self.theReply.downloadProgress.connect(lambda done,  all,  status="download": self.showProgressBar(done,  all,  status))
        
    def getResultFile(self, identifier, mimeType, encoding, schema,  reply):
        # Check if there is redirection        
        try:
            reDir = reply.attribute(QNetworkRequest.RedirectionTargetAttribute).toUrl()
            if not reDir.isEmpty():
                    self.fetchResult(encoding, schema,  reDir, identifier, mimeType)
                    return
                
        except:
            reDir = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
            if reDir is not None:
                self.fetchResult(encoding, schema,  reDir, identifier, mimeType)
                return
                
        self._resultFileCallback(identifier, mimeType, encoding, schema,  reply)
        self.noFilesToFetch -= 1
        reply.deleteLater()

    def handleEncoded(self, file, mimeType, encoding,  schema):
        # Decode?
        if schema == "base64" or encoding == 'base64':
            return decodeBase64(file, mimeType)
        else:
            return file

    def showProgressBar(self,  done,  total , status):
        
        complete = status == "aborted" or status == "finished" or status == "error"

        self.statusLabel.setText(status)

        self.progressBar.setRange(done, total)
        if status == "upload" and done == total:
            status = "processing"
            done = total = 0

        if complete:
            self.progressBar.setRange(0, 100)
            self.progressBar.setValue(100)
        else:
            self.progressBar.setRange(0, total)
            self.progressBar.setValue(done)       
        
    def errorHandler(self, resultXML):
         if resultXML:
           qDebug(resultXML)
           query = QXmlQuery(QXmlQuery.XSLT20)
           xslFile = QFile(":/plugins/QgsWPSClient/exception.xsl")
           xslFile.open(QIODevice.ReadOnly)
           bRead = query.setFocus(resultXML)
           query.setQuery(xslFile)
           exceptionHtml = query.evaluateToString()
           if exceptionHtml is None:
               qDebug("Empty result from exception.xsl")
               exceptionHtml = resultXML
           self._errorResultCallback(exceptionHtml)
           xslFile.close()
         return False
