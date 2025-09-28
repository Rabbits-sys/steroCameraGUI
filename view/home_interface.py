# coding:utf-8
import os

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QLabel
from qfluentwidgets import FluentIcon, PrimaryPushSettingCard

from view.Ui_HomeInterface import Ui_HomeInterface
from view.Ui_HikInterface import Ui_HikInterface
from view.Ui_GuideInterface import Ui_GuideInterface
from view.Ui_StoreInterface import Ui_StoreInterface

class HomeInterface(Ui_HomeInterface, QWidget):
    """
    数据集相关卡片集合的界面封装。

    Parameters
    ----------
    parent : QWidget | None, optional
        父级窗口。
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.hikInterface = HikInterface()
        self.guideInterface = GuideInterface()
        self.storeInterface = StoreInterface()

        # 添加标签页
        self.addSubInterface(self.hikInterface, 'hikInterface', '可见光相机')
        self.addSubInterface(self.guideInterface, 'guideInterface', '红外相机')
        self.addSubInterface(self.storeInterface, 'storeInterface', '采集设置')

        # 连接信号并初始化当前标签页
        self.settingStackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.settingStackedWidget.setCurrentWidget(self.hikInterface)
        self.settingSegmentedWidget.setCurrentItem(self.hikInterface.objectName())

        self.stateStartButton.setIcon(FluentIcon.PLAY)
        self.stateGrabButton.setIcon(FluentIcon.PHOTO)

        # add shadow effect to card
        self.setShadowEffect(self.settingCard)
        self.setShadowEffect(self.stateCard)
        self.setShadowEffect(self.irCard)
        self.setShadowEffect(self.rgbCard)

    def addSubInterface(self, widget, objectName: str, text: str):
        widget.setObjectName(objectName)
        self.settingStackedWidget.addWidget(widget)

        # 使用全局唯一的 objectName 作为路由键
        self.settingSegmentedWidget.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.settingStackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.settingStackedWidget.widget(index)
        self.settingSegmentedWidget.setCurrentItem(widget.objectName())


    def setShadowEffect(self, card: QWidget):
        """
        为指定卡片添加阴影效果。

        Parameters
        ----------
        card : QWidget
            目标卡片控件。

        Returns
        -------
        None
        """
        shadowEffect = QGraphicsDropShadowEffect(self)
        shadowEffect.setColor(QColor(0, 0, 0, 15))
        shadowEffect.setBlurRadius(10)
        shadowEffect.setOffset(0, 0)
        card.setGraphicsEffect(shadowEffect)


class HikInterface(Ui_HikInterface, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.hikEnumButton.setIcon(FluentIcon.SYNC)
        self.hikOpenButton.setIcon(FluentIcon.POWER_BUTTON)

class GuideInterface(Ui_GuideInterface, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.guideLoadButton.setIcon(FluentIcon.POWER_BUTTON)
        self.guideFocalButton.setIcon(FluentIcon.SYNC)

class StoreInterface(Ui_StoreInterface, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.storeCard = PrimaryPushSettingCard(
            text="选择路径",
            icon=FluentIcon.DOWNLOAD,
            title="下载目录",
            content=os.getcwd()
        )
        self.storeCard.hBoxLayout.setSpacing(5)
        self.storeVerticalLayout_2.addWidget(self.storeCard)
