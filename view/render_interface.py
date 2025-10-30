import os

from PyQt5.QtGui import QColor, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QFrame, QVBoxLayout, QFileDialog
from qfluentwidgets import SubtitleLabel, BodyLabel, PushButton

from view.Ui_RenderInterface import Ui_RenderInterface

class DragDropArea(QFrame):
    """拖拽区域组件，支持拖拽单个温度矩阵文件(.json)或文件夹。

    Signals
    -------
    fileDropped: str
        当拖拽或浏览选择了文件时发出，参数为文件路径。
    dirDropped: str
        当拖拽或浏览选择了文件夹时发出，参数为文件夹路径。
    """
    fileDropped = pyqtSignal(str)  # 文件拖拽信号
    dirDropped = pyqtSignal(str)   # 文件夹拖拽信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.browse_btn = None
        self.browse_dir_btn = None
        self.setObjectName("dragDropArea")
        self.setAcceptDrops(True)
        self.setupUI()

    def setupUI(self):
        """设置拖拽区域UI"""
        self.setMinimumHeight(200)
        self.setStyleSheet("""
            #dragDropArea {
                border: 2px dashed #ccc;
                border-radius: 10px;
                background: transparent;
            }
            #dragDropArea:hover {
                border-color: #007ACC;
                background-color: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # 拖拽图标
        icon_label = SubtitleLabel("📁", self)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 主要提示文字
        main_text = SubtitleLabel("将 文件 或 文件夹 拖拽到此处", self)
        main_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 次要提示文字
        sub_text = BodyLabel("支持：温度矩阵 JSON 文件 (*.json) 与文件夹", self)
        sub_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 额外提示文字
        browse_text = BodyLabel("或点击下方按钮选择", self)
        browse_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 浏览文件按钮
        self.browse_btn = PushButton("选择文件", self)
        self.browse_btn.clicked.connect(self.browse_files)

        # 浏览文件夹按钮
        self.browse_dir_btn = PushButton("选择文件夹", self)
        self.browse_dir_btn.clicked.connect(self.browse_folder)

        layout.addWidget(icon_label)
        layout.addWidget(main_text)
        layout.addWidget(sub_text)
        layout.addWidget(browse_text)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.browse_dir_btn)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件：支持单个 .json 文件或文件夹"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and len(urls) == 1:
                path = urls[0].toLocalFile()
                lower = path.lower()
                if (lower.endswith('.json') and os.path.isfile(path)) or os.path.isdir(path):
                    event.acceptProposedAction()
                    self.setStyleSheet("""
                        #dragDropArea {
                            border: 2px solid #007ACC;
                            border-radius: 10px;
                            background-color: transparent;
                        }
                    """)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        """拖拽离开事件：恢复样式"""
        self.setStyleSheet("""
            #dragDropArea {
                border: 2px dashed #ccc;
                border-radius: 10px;
                background-color: transparent;
            }
            #dragDropArea:hover {
                border-color: #007ACC;
                background-color: transparent;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        """文件/文件夹拖拽释放事件"""
        urls = event.mimeData().urls()
        if urls and len(urls) == 1:
            path = urls[0].toLocalFile()
            path_lower = path.lower()
            if os.path.isdir(path) and os.path.exists(path):
                self.dirDropped.emit(path)
                event.acceptProposedAction()
            elif path_lower.endswith('.json') and os.path.isfile(path):
                self.fileDropped.emit(path)
                event.acceptProposedAction()

        # 恢复样式
        self.dragLeaveEvent(event)

    def browse_files(self):
        """浏览文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择温度矩阵 JSON 文件",
            "",
            "JSON 文件 (*.json)"
        )

        if file_path and os.path.exists(file_path):
            self.fileDropped.emit(file_path)

    def browse_folder(self):
        """浏览文件夹对话框"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            ""
        )
        if dir_path and os.path.exists(dir_path):
            self.dirDropped.emit(dir_path)

class RenderInterface(Ui_RenderInterface, QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # self.renderOneButton.setIcon(FluentIcon.PLAY)
        # self.renderAllButton.setIcon(FluentIcon.PHOTO)

        self.irLabel.setScaledContents(False)

        self.renderProgressRing.setTextVisible(True)

        self.dragDropArea = DragDropArea()

        self.settingVerticalLayout_2.addWidget(self.dragDropArea)

        self.setShadowEffect(self.settingCard)
        self.setShadowEffect(self.irCard)


    def setShadowEffect(self, card: QWidget):
        """为卡片控件添加统一阴影效果。

        Parameters
        ----------
        card : QWidget
            需要应用阴影的控件。

        Returns
        -------
        None
            无返回值，直接修改控件效果。
        """
        shadowEffect = QGraphicsDropShadowEffect(self)
        shadowEffect.setColor(QColor(0, 0, 0, 15))
        shadowEffect.setBlurRadius(10)
        shadowEffect.setOffset(0, 0)
        card.setGraphicsEffect(shadowEffect)
