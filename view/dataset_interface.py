# coding:utf-8
"""
数据集界面（CMU ARCTIC 播放预览）

概述
----
用于选择说话人组合、显示对应文本、触发“试播”操作；实际播放逻辑由上层绑定。
"""
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from qfluentwidgets import FluentIcon

from view.Ui_DatasetInterface import Ui_DatasetInterface


class DatasetInterface(Ui_DatasetInterface, QWidget):
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
        self.playPushButton.setIcon(FluentIcon.PLAY)
        # add shadow effect to card
        self.setShadowEffect(self.signalCard)
        self.setShadowEffect(self.playCard)
        self.setShadowEffect(self.stateCard)

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
