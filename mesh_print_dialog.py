# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MeshPrintDialog
                                 A QGIS plugin
                              -------------------
        copyright            : (C) 2023 by orbitalnet
 ***************************************************************************/

"""

import os

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QFont,QColor
from qgis.PyQt.QtWidgets import QFileDialog

from qgis.core import *
from qgis.utils import iface

from PyQt5.QtWidgets import QMessageBox

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'mesh_print_dialog_base.ui'))

FIELD_MESH_NO = "mesh_no"

class MeshPrintDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface,parent=None):
        """Constructor."""
        super(MeshPrintDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.iface = iface
        self.layer = None
        
        # プロジェクトのレイアウトマネージャーからレイアウト情報を取得
        layout_list = QgsProject.instance().layoutManager().printLayouts()
        for layout in layout_list:
            self.cmb_papers.addItem(layout.name())

        #　ボタンクリック時
        self.btn_create_mesh.clicked.connect(self.createArea)
        self.btn_pdf_out.clicked.connect(self.exportPdf)

    
    def createArea(self):
        """
        領域を算出してメッシュレイヤとして作成する
        """
         # 新規レイヤを作成
        self.layer = QgsVectorLayer('polygon', 'メッシュ', 'memory')

        # プロジェクトのCRSを設定
        crs = QgsProject.instance().crs()
        self.layer.setCrs(crs)

        # 属性定義
        prov = self.layer.dataProvider()
        prov.addAttributes([QgsField(FIELD_MESH_NO,QVariant.Int)])
        self.layer.updateFields()
        
        #ラベルの追加とスタイル設定
        settings = QgsPalLayerSettings()
        format = QgsTextFormat()
        format.setFont(QFont('Arial', 50))
        format.setSize(30)
        format.setColor(QColor('Green'))
        format.setSizeUnit(QgsUnitTypes.RenderMapUnits)
        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(0.5)
        buffer.setColor(QColor('white'))
        format.setBuffer(buffer)
        settings.setFormat(format)
        settings.fieldName = FIELD_MESH_NO
        settings.isExpression = True
        labels = QgsVectorLayerSimpleLabeling(settings)
        self.layer.setLabelsEnabled(True)
        self.layer.setLabeling(labels)
        self.layer.triggerRepaint()
        iface.mapCanvas().refresh()      

        # レイアウトマネージャーの情報を定義        
        l_out = QgsProject.instance().layoutManager().layoutByName(self.cmb_papers.currentText())
        if l_out == None:
            QMessageBox.warning(self, 'PDF作成', u"用紙サイズが登録されていません。", QMessageBox.Ok)
            return

        # 地図部分
        self.printmap = l_out.itemById('map')
        if self.printmap == None:
            QMessageBox.warning(self, 'PDF作成', u"レイアウトに地図表示オブジェクト'map'が登録されていません。", QMessageBox.Ok)
            return

        map_size = self.printmap.sizeWithUnits()
        map_height = map_size.height()
        map_width = map_size.width()

        # 縮尺
        zoom = self.spn_zoom_level.value()

        
        # メッシュの幅と高さ
        mesh_width = (map_width / 1000) * int(zoom)
        mesh_height = (map_height / 1000) * int(zoom)

        print("map_height", map_height)
        print("mesh_width", mesh_width)
                
        # 領域から始点取得
        startPoint = QgsPointXY(iface.mapCanvas().extent().xMinimum(), iface.mapCanvas().extent().yMaximum())
        mesh_index = 0  # 表示番号

        # ボタンは非活性        
        self.btn_create_mesh.setEnabled(False)
        self.btn_pdf_out.setEnabled(False)

        # 座標に沿ってメッシュ生成実行
        while (startPoint.y() > iface.mapCanvas().extent().yMinimum()) :
            while (startPoint.x() < iface.mapCanvas().extent().xMaximum()) :
                mesh_index = mesh_index + 1
                # メッシュ単体を作成
                self.createMesh(prov, mesh_width, mesh_height, startPoint, mesh_index)

                # 次の始点を設定
                startPoint.setX(startPoint.x() + mesh_width)

            # メッシュ改行
            startPoint = QgsPointXY(iface.mapCanvas().extent().xMinimum(),startPoint.y() - mesh_height)

        # レイヤ更新
        self.layer.updateExtents()
        QgsProject().instance().addMapLayers([self.layer])

        # ボタンを有効に戻す
        self.btn_create_mesh.setEnabled(True)
        self.btn_pdf_out.setEnabled(True)

        QMessageBox.information(self, 'メッシュ作成終了', u"メッシュを作成しました。", QMessageBox.Ok)


        
    def createMesh(self, prov, mesh_width, mesh_height, p1, val):
        """
        メッシュオブジェクトを生成する
        """

        # 始点と対角線の点による矩形
        p2 = QgsPointXY(p1.x()  + mesh_width , p1.y() - mesh_height)
        mesh =  QgsRectangle(p1,p2)

        # フィーチャ生成
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromRect(mesh))
        val = feat.setAttributes([val])
        prov.addFeatures([feat])


    def exportPdf(self):
        """
        指定したレイアウトマネージャーを用いてＰＤＦを出力する
        """

        # 入力チェック
        papers = self.cmb_papers.currentText()
        if papers == None or papers == "":
            QMessageBox.warning(self, 'PDF作成', u"用紙サイズが登録されていません。", QMessageBox.Ok)
            return

        #UI縮尺の入力値を取得
        zoom = self.spn_zoom_level.value()

        #UIのメッシュ番号を取得
        id_text = self.out_mesh_number.text()
        if id_text == None or id_text == "":
            QMessageBox.warning(self, 'PDF作成', u"出力メッシュ番号を入力してください", QMessageBox.Ok)
            return

        # 指定されたidを分解
        comm_edit = id_text.split(',') 
        idlist = []

        try:
            for id_text in comm_edit:
                # ハイフン指定
                hyphen = id_text.split('-')
                if len(hyphen) == 2:
                    start = int(hyphen[0])
                    end = int(hyphen[1])
                    while (start <= end):
                        idlist.append(start)
                        start = start +1
                else:
                    # そのまま追加
                    idlist.append(int(id_text))   
        except ValueError:
            # 入力エラー
            QMessageBox.warning(self, 'PDF作成', u"出力メッシュ番号は数値を入力してください", QMessageBox.Ok)
            return

        # ディレクトリ選択ダイアログを表示
        dirName = QFileDialog.getExistingDirectory(self, '出力先フォルダ', os.path.expanduser('~') + '/Desktop')

        # メッシュは一時非表示
        pry= QgsProject.instance()

        if self.layer == None:
            mesh_layers = QgsProject.instance().mapLayersByName('メッシュ')
            if mesh_layers != None and len(mesh_layers) > 0:
                self.layer = mesh_layers[0]

        if self.layer == None:
            # レイヤがないエラー
            QMessageBox.warning(self, 'PDF作成', u"メッシュタイルを作成してください", QMessageBox.Ok)
            return

        pry.layerTreeRoot().findLayer(self.layer).setItemVisibilityChecked(False)

        # メッシュ番号でループ
        l_out = QgsProject.instance().layoutManager().layoutByName(self.cmb_papers.currentText())
        for idx in idlist:
            req =QgsFeatureRequest().setFilterExpression('"' + FIELD_MESH_NO + '"=' + str(idx) + '')
            features = self.layer.getFeatures(req)

            # 番号は一意
            for feature in features:
                # レイアウトマネージャーアイテムの取得
                printmap = l_out.itemById('map') #存在チェック済み
                printmap.__class__ = QgsLayoutItemMap
                printmap.setExtent(feature.geometry().boundingBox())
                printmap.setScale(int(zoom))

                # 用紙サイズと番号のファイル名
                file_name = self.cmb_papers.currentText() + ('_') + str(idx) + ".pdf"

                exporter =  QgsLayoutExporter(l_out)
                exporter.exportToPdf(os.path.join(dirName,file_name),
                                    QgsLayoutExporter.PdfExportSettings())

        # 一時非表示を戻す
        pry.layerTreeRoot().findLayer(self.layer).setItemVisibilityChecked(True)

        # 正常終了のメッセージ
        QMessageBox.information(self, 'PDF作成終了', u"PDFを右記フォルダに出力しました。【" + dirName + "】", QMessageBox.Ok)

