# coding:utf-8
import os
import sys
import json
import logging
import ctypes as ct
from datetime import datetime

logging.basicConfig(filename='program.log', filemode='w', level=logging.DEBUG)

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QSize, QSettings, QTimer, QEventLoop
from PyQt5.QtGui import QIcon, QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QFileDialog
from qfluentwidgets import ( setTheme, Theme, InfoBar, InfoBarPosition,
                            SplitFluentWindow, FluentTranslator, SplashScreen)
from qfluentwidgets import FluentIcon as FIF

from view.home_interface import HomeInterface

from driver.guideDriver import IRCamera
from driver.hikDriver import RGBCamera
from storeManage import StoreManage

logger = logging.getLogger(__name__)

class Window(SplitFluentWindow):
    sigShowIrVideo = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()
        # running flag
        self.rgbOpenFlag = False
        self.rgbBusyFlag = False
        self.irOpenFlag = False
        self.irBusyFlag = False


        # create sub interface
        self.homeInterface = HomeInterface(self)

        self.initNavigation()
        self.initWindow()

        # create splash screen and show window
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(200, 200))
        self.show()
        loop = QEventLoop(self)
        QTimer.singleShot(500, loop.quit)
        loop.exec()

        self.paramConfig: Optional[QSettings] = None
        self.rgbDriver = RGBCamera()
        self.irDriver = IRCamera()

        self.storeManage = StoreManage()

        self.initParam()
        self.initDisplay()
        self.initSlot()

        self.splashScreen.finish()

    def initNavigation(self):
        # add sub interface
        self.addSubInterface(self.homeInterface, FIF.HOME, '主页')

        self.navigationInterface.setExpandWidth(140)

    def initWindow(self):
        self.resize(1700, 800)
        self.setWindowIcon(QIcon('resource/images/logo.ico'))
        self.setWindowTitle('浮力工业——相机采集工具')

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)

    def initSettings(self):
        self.paramConfig = QSettings('config.ini', QSettings.IniFormat)

    def initParam(self):
        # load settings
        if not os.path.exists('config.ini'):
            InfoBar.info(
                title='[参数加载]',
                content='创建配置文件 config.ini',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=-1,
                parent=self
            )

            self.initSettings()
            # init the paramConfig
            self.irDriver.param.reset_param_of_file(self.paramConfig)
            self.storeManage.reset_param_of_file(self.paramConfig)
        else:
            self.initSettings()
            if self.irDriver.param.load_param_from_file(self.paramConfig):
                InfoBar.warning(
                    title='[参数加载]',
                    content='IR 驱动参数不合法，已重置',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=-1,
                    parent=self
                )

            if self.storeManage.load_param_from_file(self.paramConfig):
                InfoBar.warning(
                    title='[参数加载]',
                    content='存储参数不合法，已重置',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=-1,
                    parent=self
                )

    def initDisplay(self):
        self.homeInterface.guideInterface.guideIpLineEdit.setText(self.irDriver.param.server)
        self.homeInterface.guideInterface.guidePortLineEdit.setText(str(self.irDriver.param.port))
        self.homeInterface.guideInterface.guideUserLineEdit.setText(self.irDriver.param.username)
        self.homeInterface.guideInterface.guidePasswordLineEdit.setText(self.irDriver.param.password)

        self.homeInterface.storeInterface.storeCard.setContent(self.storeManage.store_path)
        self.homeInterface.storeInterface.storeRgbCheckBox_1.blockSignals(True)
        self.homeInterface.storeInterface.storeIrCheckBox_1.blockSignals(True)
        self.homeInterface.storeInterface.storeIrCheckBox_2.blockSignals(True)
        self.homeInterface.storeInterface.storeRgbCheckBox_1.setChecked(self.storeManage.save_rgb_img)
        self.homeInterface.storeInterface.storeIrCheckBox_1.setChecked(self.storeManage.save_ir_img)
        self.homeInterface.storeInterface.storeIrCheckBox_2.setChecked(self.storeManage.save_ir_temp)
        self.homeInterface.storeInterface.storeRgbCheckBox_1.blockSignals(False)
        self.homeInterface.storeInterface.storeIrCheckBox_1.blockSignals(False)
        self.homeInterface.storeInterface.storeIrCheckBox_2.blockSignals(False)

        self.stateDisplay()

    def initSlot(self):
        # hik
        self.homeInterface.hikInterface.hikEnumButton.clicked.connect(self.hikEnumButtonClicked)
        self.homeInterface.hikInterface.hikOpenButton.toggled.connect(lambda checked: self.hikOpenButtonClicked(checked))
        self.homeInterface.hikInterface.hikGainSlider.sliderReleased.connect(self.hikGainSliderReleased)
        self.homeInterface.hikInterface.hikExposeSlider.sliderReleased.connect(self.hikExposeSliderReleased)
        self.homeInterface.hikInterface.hikFrameRateSlider.sliderReleased.connect(self.hikFrameRateSliderReleased)

        # guide
        self.homeInterface.guideInterface.guideLoadButton.toggled.connect(lambda checked: self.guideLoadButtonClicked(checked))
        self.homeInterface.guideInterface.guideColorCheckBox.clicked.connect(self.guideColorCheckClicked)
        self.homeInterface.guideInterface.guideColorComboBox.currentIndexChanged.connect(self.guideColorComboChanged)
        self.homeInterface.guideInterface.guideFocalButton.clicked.connect(self.guideFocalButtonClicked)
        self.sigShowIrVideo.connect(self.onShowIrVideo)

        # store
        self.homeInterface.storeInterface.storeCard.clicked.connect(self.storeCardClicked)
        self.homeInterface.storeInterface.storeRgbCheckBox_1.clicked.connect(self.storeRgbCheckBox_1Changed)
        self.homeInterface.storeInterface.storeIrCheckBox_1.clicked.connect(self.storeIrCheckBox_1Changed)
        self.homeInterface.storeInterface.storeIrCheckBox_2.clicked.connect(self.storeIrCheckBox_2Changed)

        self.homeInterface.stateStartButton.toggled.connect(lambda checked: self.startButtonClicked(checked))
        self.homeInterface.stateGrabButton.clicked.connect(self.stateGrabButtonClicked)

    def hikEnumButtonClicked(self):
        if self.rgbOpenFlag or self.rgbBusyFlag:
            InfoBar.warning(
                title='[RGB相机]',
                content='请关闭相机后执行遍历！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            return
        self.homeInterface.hikInterface.hikEnumComboBox.clear()
        ret, devList = self.rgbDriver.hk_enum_devices()
        if ret:
            InfoBar.warning(
                title='[RGB相机]',
                content='遍历相机失败！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            self.hikOpenFrozen()
            return
        self.homeInterface.hikInterface.hikEnumComboBox.addItems(devList)
        self.homeInterface.hikInterface.hikEnumComboBox.setCurrentIndex(0)
        self.hikOpenUnfrozen()
        # display

    def hikOpenButtonClicked(self, checked):
        if checked:
            if self.rgbBusyFlag:
                InfoBar.warning(
                    title='[RGB相机]',
                    content='请结束采集后执行关机！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.homeInterface.hikInterface.hikOpenButton.blockSignals(True)
                self.homeInterface.hikInterface.hikOpenButton.setChecked(False)
                self.homeInterface.hikInterface.hikOpenButton.blockSignals(False)
            elif self.rgbOpenFlag:
                _ = self.rgbDriver.hk_close_device()
                self.rgbOpenFlag = False
                self.rgbDriver.param.reset_param()

                self.homeInterface.hikInterface.hikOpenButton.setText("打开设备")

                self.hikEnumUnfrozen()
                self.hikParamFrozen()
            else:
                InfoBar.info(
                    title='[RGB相机]',
                    content='重复关机！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.hikEnumUnfrozen()
                self.hikParamFrozen()
        else:
            if self.rgbOpenFlag:
                InfoBar.info(
                    title='[RGB相机]',
                    content='重复开机！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.hikEnumFrozen()
                self.hikParamUnfrozen()
            else:
                nSelCamIndex = self.homeInterface.hikInterface.hikEnumComboBox.currentIndex()
                if nSelCamIndex < 0:
                    InfoBar.error(
                        title='[RGB相机]',
                        content='未选中相机！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.homeInterface.hikInterface.hikOpenButton.blockSignals(True)
                    self.homeInterface.hikInterface.hikOpenButton.setChecked(True)
                    self.homeInterface.hikInterface.hikOpenButton.blockSignals(False)
                else:
                    ret = self.rgbDriver.hk_open_device(nSelCamIndex)
                    if ret:
                        InfoBar.error(
                            title='[RGB相机]',
                            content='相机开机失败！',
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.BOTTOM_RIGHT,
                            duration=2000,
                            parent=self
                        )

                        _ = self.rgbDriver.hk_close_device()

                        self.homeInterface.hikInterface.hikOpenButton.blockSignals(True)
                        self.homeInterface.hikInterface.hikOpenButton.setChecked(True)
                        self.homeInterface.hikInterface.hikOpenButton.blockSignals(False)
                    else:
                        self.rgbOpenFlag = True

                        self.rgbDriver.hk_get_param()

                        self.homeInterface.hikInterface.hikFrameRateSlider.setValue(int(self.rgbDriver.param.frame_rate))
                        self.homeInterface.hikInterface.hikExposeSlider.setValue(int(self.rgbDriver.param.exposure_time))
                        self.homeInterface.hikInterface.hikGainSlider.setValue(int(self.rgbDriver.param.gain))

                        self.homeInterface.hikInterface.hikOpenButton.setText("关闭设备")

                        self.hikEnumFrozen()
                        self.hikParamUnfrozen()
        self.stateDisplay()

    def hikGainSliderReleased(self):
        value = self.homeInterface.hikInterface.hikGainSlider.value()
        self.rgbDriver.param.set_gain(value)
        self.rgbDriver.hk_set_param()
        self.stateDisplay()

    def hikExposeSliderReleased(self):
        value = self.homeInterface.hikInterface.hikExposeSlider.value()
        self.rgbDriver.param.set_exposure_time(value)
        self.rgbDriver.hk_set_param()
        self.stateDisplay()

    def hikFrameRateSliderReleased(self):
        value = self.homeInterface.hikInterface.hikFrameRateSlider.value()
        self.rgbDriver.param.set_frame_rate(value)
        self.rgbDriver.hk_set_param()
        self.stateDisplay()

    # guide
    def guideLoadButtonClicked(self, checked):
        if checked:
            if self.irBusyFlag:
                InfoBar.warning(
                    title='[IR相机]',
                    content='请结束采集后执行关机！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.homeInterface.guideInterface.guideLoadButton.blockSignals(True)
                self.homeInterface.guideInterface.guideLoadButton.setChecked(False)
                self.homeInterface.guideInterface.guideLoadButton.blockSignals(False)
            elif self.irOpenFlag:
                _ = self.irDriver.logout()
                self.irOpenFlag = False

                self.homeInterface.guideInterface.guideLoadButton.setText("登录设备")

                self.guideParamUnfrozen()
                self.guideOperationFrozen()
            else:
                InfoBar.info(
                    title='[IR相机]',
                    content='重复关机！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.guideParamUnfrozen()
                self.guideOperationFrozen()
        else:
            if self.irOpenFlag:
                InfoBar.info(
                    title='[IR相机]',
                    content='重复开机！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.guideParamFrozen()
                self.guideOperationUnfrozen()
            else:
                ret = self.irDriver.param.set_server(self.homeInterface.guideInterface.guideIpLineEdit.text())
                ret |= self.irDriver.param.set_port(self.homeInterface.guideInterface.guidePortLineEdit.text())
                ret |= self.irDriver.param.set_username(self.homeInterface.guideInterface.guideUserLineEdit.text())
                ret |= self.irDriver.param.set_password(self.homeInterface.guideInterface.guidePasswordLineEdit.text())

                if ret:
                    InfoBar.error(
                        title='[IR相机]',
                        content='登录参数不合法！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.homeInterface.guideInterface.guideLoadButton.blockSignals(True)
                    self.homeInterface.guideInterface.guideLoadButton.setChecked(True)
                    self.homeInterface.guideInterface.guideLoadButton.blockSignals(False)
                else:
                    ret = self.irDriver.login()
                    if ret:
                        InfoBar.error(
                            title='[IR相机]',
                            content='相机开机失败！',
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.BOTTOM_RIGHT,
                            duration=2000,
                            parent=self
                        )

                        _ = self.irDriver.logout()

                        self.homeInterface.guideInterface.guideLoadButton.blockSignals(True)
                        self.homeInterface.guideInterface.guideLoadButton.setChecked(True)
                        self.homeInterface.guideInterface.guideLoadButton.blockSignals(False)
                    else:
                        self.irOpenFlag = True

                        self.initSettings()
                        self.irDriver.param.save_param_to_file(self.paramConfig)

                        ret, p = self.irDriver.get_thermometry_param()
                        if ret:
                            InfoBar.warning(
                                title='[IR相机]',
                                content='获取测温参数失败！',
                                orient=Qt.Horizontal,
                                isClosable=True,
                                position=InfoBarPosition.BOTTOM_RIGHT,
                                duration=2000,
                                parent=self
                            )
                        else:
                            self.homeInterface.guideInterface.guideColorCheckBox.blockSignals(True)
                            self.homeInterface.guideInterface.guideColorComboBox.blockSignals(True)
                            self.homeInterface.guideInterface.guideColorCheckBox.setChecked(p.color_show == 1)
                            self.homeInterface.guideInterface.guideColorComboBox.setCurrentIndex(max(0, int(p.color_bar) - 1))
                            self.homeInterface.guideInterface.guideColorCheckBox.blockSignals(False)
                            self.homeInterface.guideInterface.guideColorComboBox.blockSignals(False)
                        self.homeInterface.guideInterface.guideLoadButton.setText("登出设备")

                        self.guideParamFrozen()
                        self.guideOperationUnfrozen()
        self.stateDisplay()

    def guideColorCheckClicked(self):
        ret, p = self.irDriver.get_thermometry_param()
        if ret:
            InfoBar.warning(
                title='[IR相机]',
                content='获取测温参数失败！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            p.color_show = 1 if self.homeInterface.guideInterface.guideColorCheckBox.isChecked() else 0
            ret = self.irDriver.set_thermometry_param(p)
            if ret:
                InfoBar.error(
                    title='[IR相机]',
                    content='设置测温参数失败！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
        self.stateDisplay()

    def guideColorComboChanged(self):
        ret, p = self.irDriver.get_thermometry_param()
        if ret:
            InfoBar.warning(
                title='[IR相机]',
                content='获取测温参数失败！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            p.color_bar = self.homeInterface.guideInterface.guideColorComboBox.currentIndex() + 1
            ret = self.irDriver.set_thermometry_param(p)
            if ret:
                InfoBar.error(
                    title='[IR相机]',
                    content='设置测温参数失败！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
        self.stateDisplay()

    def guideFocalButtonClicked(self):
        if not self.irOpenFlag:
            InfoBar.warning(
                title='[IR相机]',
                content='请先登录设备！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            return
        ret = self.irDriver.set_focus(5, 0)
        if ret:
            InfoBar.error(
                title='[IR相机]',
                content='自动调焦失败！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )

    def onShowIrVideo(self, image: QImage):
        if self.irDriver._logged_in:
            self.homeInterface.irLabel.setPixmap(QPixmap.fromImage(image))
        else:
            self.homeInterface.irLabel.clear()

    def _on_rtsp(self, outdata, w, h, user):
        try:
            if not outdata or w <= 0 or h <= 0:
                return
            size = int(w) * int(h) * 3
            buf = ct.string_at(outdata, size)
            img = QImage(buf, int(w), int(h), int(w) * 3, QImage.Format_RGB888).copy()
            self.sigShowIrVideo.emit(img)
        except Exception:
            pass

    def storeCardClicked(self):
        storePath = QFileDialog.getExistingDirectory(
            self,
            '选择路径',
            os.getcwd(),
            )
        if storePath:
            self.storeManage.set_store_path(storePath)
            self.homeInterface.storeInterface.storeCard.setContent(storePath)

            self.initSettings()
            self.storeManage.save_param_to_file(self.paramConfig)

    def storeRgbCheckBox_1Changed(self):
        flag = self.homeInterface.storeInterface.storeRgbCheckBox_1.isChecked()
        self.storeManage.set_save_rgb_img(flag)
        self.initSettings()
        self.storeManage.save_param_to_file(self.paramConfig)

    def storeIrCheckBox_1Changed(self):
        flag = self.homeInterface.storeInterface.storeIrCheckBox_1.isChecked()
        self.storeManage.set_save_ir_img(flag)
        self.initSettings()
        self.storeManage.save_param_to_file(self.paramConfig)

    def storeIrCheckBox_2Changed(self):
        flag = self.homeInterface.storeInterface.storeIrCheckBox_2.isChecked()
        self.storeManage.set_save_ir_temp(flag)
        self.initSettings()
        self.storeManage.save_param_to_file(self.paramConfig)

    def startButtonClicked(self, checked):
        if checked:
            if not self.rgbBusyFlag and not self.irBusyFlag:
                InfoBar.info(
                    title='[采样]',
                    content='重复关闭采样！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.stateGrubFrozen()
                self.storeOperationUnfrozen()
            else:
                if self.rgbBusyFlag:
                    ret = self.rgbDriver.hk_stop_grabbing()
                    if ret:
                        InfoBar.warning(
                            title='[RGB相机]',
                            content='关闭采样失败！',
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.BOTTOM_RIGHT,
                            duration=2000,
                            parent=self
                        )
                    self.rgbBusyFlag = False

                if self.irBusyFlag:
                    ret = self.irDriver.close_ir_video()
                    if ret:
                        InfoBar.warning(
                            title='[IR相机]',
                            content='关闭采样失败！',
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.BOTTOM_RIGHT,
                            duration=2000,
                            parent=self
                        )
                    self.irBusyFlag = False

                self.homeInterface.stateStartButton.setText("开始采样")

                self.stateGrubFrozen()
                self.storeOperationUnfrozen()
        else:
            if self.rgbBusyFlag or self.irBusyFlag:
                InfoBar.info(
                    title='[采集]',
                    content='重复开启！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.stateGrubUnfrozen()
                self.storeOperationFrozen()
            elif self.rgbOpenFlag and self.irOpenFlag:
                ret = self.rgbDriver.hk_start_grabbing(self.homeInterface.rgbWidget.winId())
                if ret:
                    InfoBar.error(
                        title='[采样]',
                        content='RGB相机采样开启失败！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    _ = self.rgbDriver.hk_stop_grabbing()
                    self.homeInterface.stateStartButton.blockSignals(True)
                    self.homeInterface.stateStartButton.setChecked(True)
                    self.homeInterface.stateStartButton.blockSignals(False)
                    return
                else:
                    self.rgbBusyFlag = True

                ret = self.irDriver.open_ir_video(self._on_rtsp, None)
                if ret:
                    InfoBar.error(
                        title='[采样]',
                        content='IR相机采样开启失败！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.irDriver.close_ir_video()
                    self.homeInterface.stateStartButton.blockSignals(True)
                    self.homeInterface.stateStartButton.setChecked(True)
                    self.homeInterface.stateStartButton.blockSignals(False)
                else:
                    self.irBusyFlag = True

                    self.homeInterface.stateStartButton.setText("结束采样")

                    self.stateGrubUnfrozen()
                    self.storeOperationFrozen()

            elif self.rgbOpenFlag:
                ret = self.rgbDriver.hk_start_grabbing(self.homeInterface.rgbWidget.winId())
                if ret:
                    InfoBar.error(
                        title='[采样]',
                        content='RGB相机采样开启失败！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    _ = self.rgbDriver.hk_stop_grabbing()
                    self.homeInterface.stateStartButton.blockSignals(True)
                    self.homeInterface.stateStartButton.setChecked(True)
                    self.homeInterface.stateStartButton.blockSignals(False)
                else:
                    self.rgbBusyFlag = True

                    self.homeInterface.stateStartButton.setText("结束采样")

                    self.stateGrubUnfrozen()
                    self.storeOperationFrozen()
            elif self.irOpenFlag:
                ret = self.irDriver.open_ir_video(self._on_rtsp, None)
                if ret:
                    InfoBar.error(
                        title='[采样]',
                        content='IR相机采样开启失败！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.irDriver.close_ir_video()
                    self.homeInterface.stateStartButton.blockSignals(True)
                    self.homeInterface.stateStartButton.setChecked(True)
                    self.homeInterface.stateStartButton.blockSignals(False)
                else:
                    self.irBusyFlag = True

                    self.homeInterface.stateStartButton.setText("结束采样")

                    self.stateGrubUnfrozen()
                    self.storeOperationFrozen()
            else:
                InfoBar.warning(
                    title='[采样]',
                    content='请至少开启一个相机！',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.homeInterface.stateStartButton.blockSignals(True)
                self.homeInterface.stateStartButton.setChecked(True)
                self.homeInterface.stateStartButton.blockSignals(False)
        self.stateDisplay()

    def stateGrabButtonClicked(self):
        if not self.rgbBusyFlag and not self.irBusyFlag:
            InfoBar.warning(
                title='[采样]',
                content='请先开启采样！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )
            return

        nowTime = datetime.now().strftime("%Y%m%d%H%M%S")
        fileName = os.path.join(self.storeManage.store_path, nowTime)
        if self.rgbBusyFlag:
            if self.storeManage.save_rgb_img:
                ret = self.rgbDriver.hk_save_jpg(fileName + '_rgb.jpg')
                if ret:
                    InfoBar.error(
                        title='[RGB相机]',
                        content='抓拍失败！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    return

        if self.irBusyFlag:
            if self.storeManage.save_ir_img:
                ret = self.irDriver.get_heatmap(fileName + '_ir.jpg')
                if ret:
                    InfoBar.error(
                        title='[IR相机]',
                        content='抓拍失败！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )

            if self.storeManage.save_ir_temp:
                ret, temp = self.irDriver.get_image_temps(384 * 512)
                if ret:
                    InfoBar.error(
                        title='[IR相机]',
                        content='抓拍失败！',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=2000,
                        parent=self
                    )
                else:
                    with open(fileName + '_temp.json', 'w') as f:
                        json.dump(temp, f)

            InfoBar.success(
                title='[采集]',
                content='抓拍成功:%s' % nowTime,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=self
            )

    def stateDisplay(self):
        rgbOpen = self.rgbOpenFlag
        rgbBusy = self.rgbBusyFlag
        exposureTime = self.rgbDriver.param.exposure_time
        gain = self.rgbDriver.param.gain
        frameRate = self.rgbDriver.param.frame_rate

        irOpen = self.irOpenFlag
        irBusy = self.irBusyFlag
        irColorUsage = self.homeInterface.guideInterface.guideColorCheckBox.isChecked()
        irColorCode = self.homeInterface.guideInterface.guideColorComboBox.currentIndex()

        stateBrowserMarkdown = ""
        stateBrowserMarkdown += "#### 📸 **RGB 相机**:\n"
        if rgbOpen:
            stateBrowserMarkdown += "##### 状态: 已开启 | "
        else:
            stateBrowserMarkdown += "##### 状态: 已关闭 | "
        if rgbBusy:
            stateBrowserMarkdown += "采样: 进行中\n"
        else:
            stateBrowserMarkdown += "采样: 已停止\n"
        if rgbOpen:
            stateBrowserMarkdown += "##### 曝光时间: " + str(exposureTime) + "us\n"
            stateBrowserMarkdown += "##### 增益: " + str(gain) + "\n"
            stateBrowserMarkdown += "##### 帧率: " + str(frameRate) + " fps\n"

        stateBrowserMarkdown += "#### 📹 **IR 相机**: \n"
        if irOpen:
            stateBrowserMarkdown += "##### 状态: 已开启 | "
        else:
            stateBrowserMarkdown += "##### 状态: 已关闭 | "
        if irBusy:
            stateBrowserMarkdown += "采样: 进行中\n"
        else:
            stateBrowserMarkdown += "采样: 已停止\n"
        if irOpen:
            if irColorUsage:
                stateBrowserMarkdown += "##### 色带: 已开启\n"
            else:
                stateBrowserMarkdown += "##### 色带: 已关闭\n"
            stateBrowserMarkdown += "##### 色彩映射编号: " + str(irColorCode) + "\n"

        self.homeInterface.stateTextBrowser.setMarkdown(stateBrowserMarkdown)

    def hikEnumFrozen(self):
        self.homeInterface.hikInterface.hikEnumButton.setEnabled(False)
        self.homeInterface.hikInterface.hikEnumComboBox.setEnabled(False)

    def hikEnumUnfrozen(self):
        self.homeInterface.hikInterface.hikEnumButton.setEnabled(True)
        self.homeInterface.hikInterface.hikEnumComboBox.setEnabled(True)

    def hikOpenFrozen(self):
        self.homeInterface.hikInterface.hikOpenButton.setEnabled(False)

    def hikOpenUnfrozen(self):
        self.homeInterface.hikInterface.hikOpenButton.setEnabled(True)

    def hikParamFrozen(self):
        self.homeInterface.hikInterface.hikGainSlider.setEnabled(False)
        self.homeInterface.hikInterface.hikExposeSlider.setEnabled(False)
        self.homeInterface.hikInterface.hikFrameRateSlider.setEnabled(False)

    def hikParamUnfrozen(self):
        self.homeInterface.hikInterface.hikGainSlider.setEnabled(True)
        self.homeInterface.hikInterface.hikExposeSlider.setEnabled(True)
        self.homeInterface.hikInterface.hikFrameRateSlider.setEnabled(True)

    def guideParamFrozen(self):
        self.homeInterface.guideInterface.guideIpLineEdit.setEnabled(False)
        self.homeInterface.guideInterface.guidePortLineEdit.setEnabled(False)
        self.homeInterface.guideInterface.guideUserLineEdit.setEnabled(False)
        self.homeInterface.guideInterface.guidePasswordLineEdit.setEnabled(False)

    def guideParamUnfrozen(self):
        self.homeInterface.guideInterface.guideIpLineEdit.setEnabled(True)
        self.homeInterface.guideInterface.guidePortLineEdit.setEnabled(True)
        self.homeInterface.guideInterface.guideUserLineEdit.setEnabled(True)
        self.homeInterface.guideInterface.guidePasswordLineEdit.setEnabled(True)

    def guideOperationFrozen(self):
        self.homeInterface.guideInterface.guideColorCheckBox.setEnabled(False)
        self.homeInterface.guideInterface.guideColorComboBox.setEnabled(False)
        self.homeInterface.guideInterface.guideFocalButton.setEnabled(False)

    def guideOperationUnfrozen(self):
        self.homeInterface.guideInterface.guideColorCheckBox.setEnabled(True)
        self.homeInterface.guideInterface.guideColorComboBox.setEnabled(True)
        self.homeInterface.guideInterface.guideFocalButton.setEnabled(True)

    def storeOperationFrozen(self):
        self.homeInterface.storeInterface.storeCard.setEnabled(False)
        self.homeInterface.storeInterface.storeRgbCheckBox_1.setEnabled(False)
        self.homeInterface.storeInterface.storeIrCheckBox_1.setEnabled(False)
        self.homeInterface.storeInterface.storeIrCheckBox_2.setEnabled(False)

    def storeOperationUnfrozen(self):
        self.homeInterface.storeInterface.storeCard.setEnabled(True)
        self.homeInterface.storeInterface.storeRgbCheckBox_1.setEnabled(True)
        self.homeInterface.storeInterface.storeIrCheckBox_1.setEnabled(True)
        self.homeInterface.storeInterface.storeIrCheckBox_2.setEnabled(True)

    def stateGrubFrozen(self):
        self.homeInterface.stateGrabButton.setEnabled(False)

    def stateGrubUnfrozen(self):
        self.homeInterface.stateGrabButton.setEnabled(True)

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
