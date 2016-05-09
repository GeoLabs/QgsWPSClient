# -*- coding: utf-8 -*-
"""
***************************************************************************
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
  ***************************************************************************
"""
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from QgsWPSClient import version
from ui_qgswpsdescribeprocess import Ui_QgsWpsDescribeProcessGUI
import os, sys, string

class QgsWpsDescribeProcessGui(QDialog, QObject, Ui_QgsWpsDescribeProcessGUI):

  def __init__(self, parent, fl):
    QDialog.__init__(self, parent, fl)
    self.setupUi(self)
    self.setWindowTitle('QgsWPSClient-'+version())
    self.selectedServiceName = parent.cmbConnections.currentText()
    
    
  def currentServiceName(self):
      return self.selectedServiceName 
