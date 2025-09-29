# coding:utf-8
"""home_interface
=================

主界面与各功能子界面封装。

本模块提供:
1. HomeInterface: 主容器，组织分段按钮与堆叠窗口。
2. HikInterface: 可见光相机操作界面。
3. GuideInterface: 红外相机操作界面。
4. StoreInterface: 采集存储参数界面。

设计要点
--------
- 分段选择控件通过对象名称 (objectName) 作为路由键避免重复。
- 阴影效果通过统一方法设置，提升界面一致性。

示例
----
>>> from view.home_interface import HomeInterface
>>> w = HomeInterface()
>>> w.addSubInterface(w.hikInterface, 'hikInterface', '可见光相机')

"""
import os

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QLabel
from qfluentwidgets import FluentIcon, PrimaryPushSettingCard

from view.Ui_HomeInterface import Ui_HomeInterface
from view.Ui_HikInterface import Ui_HikInterface
from view.Ui_GuideInterface import Ui_GuideInterface
from view.Ui_StoreInterface import Ui_StoreInterface


class HomeInterface(Ui_HomeInterface, QWidget):
    """主界面：包含相机、红外、存储等子界面。

    Parameters
    ----------
    parent : QWidget, optional
        父级窗口。

    Attributes
    ----------
    hikInterface : HikInterface
        可见光相机子界面。
    guideInterface : GuideInterface
        红外相机子界面。
    storeInterface : StoreInterface
        采集与存储参数子界面。
    settingStackedWidget : QStackedWidget
        中央堆叠窗口（由 UI 生成）。
    settingSegmentedWidget : SegmentedWidget
        顶部/侧边分段选择控件（由 UI 生成）。
    stateStartButton : QAbstractButton
        采样开始/结束按钮。
    stateGrabButton : QAbstractButton
        抓拍按钮。
    irLabel : QLabel
        显示红外图像的标签。
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.hikInterface = HikInterface()
        self.guideInterface = GuideInterface()
        self.storeInterface = StoreInterface()

        self.addSubInterface(self.hikInterface, 'hikInterface', '可见光相机')
        self.addSubInterface(self.guideInterface, 'guideInterface', '红外相机')
        self.addSubInterface(self.storeInterface, 'storeInterface', '采集设置')

        self.settingStackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.settingStackedWidget.setCurrentWidget(self.hikInterface)
        self.settingSegmentedWidget.setCurrentItem(self.hikInterface.objectName())

        self.stateStartButton.setIcon(FluentIcon.PLAY)
        self.stateGrabButton.setIcon(FluentIcon.CAMERA)

        self.irLabel.setScaledContents(True)

        self.setShadowEffect(self.settingCard)
        self.setShadowEffect(self.stateCard)
        self.setShadowEffect(self.irCard)
        self.setShadowEffect(self.rgbCard)

    def addSubInterface(self, widget, objectName: str, text: str):
        """注册并显示一个子界面。

        Parameters
        ----------
        widget : QWidget
            子界面实例。
        objectName : str
            该子界面唯一对象名称，用作路由键。
        text : str
            分段选择控件中显示的文本。

        Notes
        -----
        - objectName 需全局唯一。
        - 点击分段按钮后切换堆叠窗口当前页。
        """
        widget.setObjectName(objectName)
        self.settingStackedWidget.addWidget(widget)
        self.settingSegmentedWidget.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.settingStackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        """堆叠窗口索引改变回调。

        同步分段控件的当前项。

        Parameters
        ----------
        index : int
            新激活页面索引。
        """
        widget = self.settingStackedWidget.widget(index)
        self.settingSegmentedWidget.setCurrentItem(widget.objectName())

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


class HikInterface(Ui_HikInterface, QWidget):
    """可见光相机界面。

    负责：
    - 遍历/选择设备
    - 打开/关闭设备
    - 调节曝光、帧率、增益
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.hikEnumButton.setIcon(FluentIcon.SYNC)
        self.hikOpenButton.setIcon(FluentIcon.POWER_BUTTON)

        self.hikGainSlider.setTracking(False)
        self.hikExposeSlider.setTracking(False)


class GuideInterface(Ui_GuideInterface, QWidget):
    """红外相机界面。

    功能：登录/登出、色带开关与选择、自动调焦。
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.guideLoadButton.setIcon(FluentIcon.POWER_BUTTON)
        self.guideFocalButton.setIcon(FluentIcon.SYNC)


class StoreInterface(Ui_StoreInterface, QWidget):
    """采集存储配置界面。

    显示与修改：存储路径、是否保存 RGB/IR/温度矩阵。
    """

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
