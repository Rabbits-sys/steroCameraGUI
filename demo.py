# coding:utf-8
import sys

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import (NavigationItemPosition, MessageBox, setTheme, Theme,
                            NavigationAvatarWidget,  SplitFluentWindow, FluentTranslator)
from qfluentwidgets import FluentIcon as FIF

from view.home_interface import HomeInterface

class Window(SplitFluentWindow):

    def __init__(self):
        super().__init__()

        # create sub interface
        self.homeInterface = HomeInterface(self)

        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        # add sub interface
        self.addSubInterface(self.homeInterface, FIF.HOME, '主页')

        self.navigationInterface.addWidget(
            routeKey='avatar',
            widget=NavigationAvatarWidget('狐狸多多', 'resource/images/fox.jpg'),
            onClick=self.showMessageBox,
            position=NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.setExpandWidth(140)

    def initWindow(self):
        self.resize(1800, 800)
        self.setWindowIcon(QIcon(':/qfluentwidgets/images/fox.jpg'))
        self.setWindowTitle('PyQt-Fluent-Widgets')

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)

    def showMessageBox(self):
        w = MessageBox(
            '支持作者🥰',
            '个人开发不易，如果这个项目帮助到了您，可以考虑给作者一个小星星⭐。您的支持就是作者开发和维护项目的动力🚀',
            self
        )
        w.yesButton.setText('给狐狸小星星！')
        w.cancelButton.setText('下次一定')

        if w.exec():
            QDesktopServices.openUrl(QUrl("https://github.com/Rabbits-sys/steroCameraGUI"))


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    setTheme(Theme.AUTO)

    app = QApplication(sys.argv)

    # install translator
    translator = FluentTranslator()
    app.installTranslator(translator)

    w = Window()
    w.show()
    app.exec_()
