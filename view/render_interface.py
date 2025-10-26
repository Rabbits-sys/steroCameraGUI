import os

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QLabel
from qfluentwidgets import FluentIcon, PrimaryPushSettingCard

from view.Ui_RenderInterface import Ui_RenderInterface

class RenderInterface(Ui_RenderInterface, QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # self.renderOneButton.setIcon(FluentIcon.PLAY)
        # self.renderAllButton.setIcon(FluentIcon.PHOTO)

        self.irLabel.setScaledContents(False)

        self.renderProgressRing.setTextVisible(True)

        self.setShadowEffect(self.settingCard)
        self.setShadowEffect(self.irCard)

        self.fileCard = PrimaryPushSettingCard(
            text="选择JSON文件",
            icon=FluentIcon.DOWNLOAD,
            title="文件路径",
            content=os.path.join(os.getcwd(), 'records')
        )
        self.fileCard.hBoxLayout.setSpacing(5)
        self.settingFileVerticalLayout.addWidget(self.fileCard)


        self.dirCard = PrimaryPushSettingCard(
            text="选择目录",
            icon=FluentIcon.DOWNLOAD,
            title="目录",
            content=os.getcwd()
        )
        self.dirCard.hBoxLayout.setSpacing(5)
        self.settingDirVerticalLayout.addWidget(self.dirCard)


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
