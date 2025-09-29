# coding:utf-8
"""demo
=======

应用程序入口模块：负责初始化 UI、驱动、参数与交互逻辑。

核心职责
--------
1. 界面框架构建（`Window` 继承自 `SplitFluentWindow`）。
2. 相机（RGB / IR）驱动生命周期管理：枚举、开关、采样、参数调整。
3. 存储管理：抓拍及实时采集参数保存。
4. 用户交互：信息提示、状态展示、参数同步。

使用示例
--------
>>> from demo import main  # 直接运行本文件亦可

说明
----
- 所有 GUI 相关操作均在主线程执行；IR 视频帧通过回调转为 Qt 信号投递。
- 参数读写基于 QSettings(INI)；非法时自动回退默认并提示。
"""
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
    """主窗口：组织界面、驱动与业务逻辑。

    Signals
    -------
    sigShowIrVideo : pyqtSignal(QImage)
        接收 IR 回调帧并在主线程刷新界面。

    Attributes
    ----------
    rgbOpenFlag : bool
        RGB 相机是否已打开。
    rgbBusyFlag : bool
        RGB 相机是否正在采样。
    irOpenFlag : bool
        IR 相机是否已登录/打开。
    irBusyFlag : bool
        IR 相机是否正在采样。
    homeInterface : HomeInterface
        主界面聚合对象。
    rgbDriver : RGBCamera
        海康相机驱动封装。
    irDriver : IRCamera
        红外相机驱动封装。
    storeManage : StoreManage
        存储管理对象。
    paramConfig : QSettings
        参数配置文件实例 (config.ini)。
    splashScreen : SplashScreen
        启动过渡界面。
    """
    sigShowIrVideo = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()
        self.rgbOpenFlag = False
        self.rgbBusyFlag = False
        self.irOpenFlag = False
        self.irBusyFlag = False

        self.homeInterface = HomeInterface(self)

        self.initNavigation()
        self.initWindow()

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

    # ------------------------------------------------------------------
    # 初始化与配置
    # ------------------------------------------------------------------
    def initNavigation(self):
        """初始化导航/子界面。"""
        self.addSubInterface(self.homeInterface, FIF.HOME, '主页')
        self.navigationInterface.setExpandWidth(140)

    def initWindow(self):
        """初始化窗口外观与居中位置。"""
        self.resize(1700, 800)
        self.setWindowIcon(QIcon(':images/logo.ico'))
        self.setWindowTitle('浮力工业——相机采集工具')
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)

    def initSettings(self):
        """创建或刷新 QSettings 实例。"""
        self.paramConfig = QSettings('config.ini', QSettings.IniFormat)

    def initParam(self):
        """加载或初始化参数。

        逻辑
        ----
        - 若配置文件不存在：创建并写入默认参数。
        - 若存在：尝试加载；若某块参数非法 -> 重置并提示。
        """
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
        """根据当前参数刷新界面默认值。"""
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
        """连接所有信号与槽。"""
        # RGB
        self.homeInterface.hikInterface.hikEnumButton.clicked.connect(self.hikEnumButtonClicked)
        self.homeInterface.hikInterface.hikOpenButton.toggled.connect(lambda checked: self.hikOpenButtonClicked(checked))
        self.homeInterface.hikInterface.hikGainSlider.sliderReleased.connect(self.hikGainSliderReleased)
        self.homeInterface.hikInterface.hikExposeSlider.sliderReleased.connect(self.hikExposeSliderReleased)
        self.homeInterface.hikInterface.hikFrameRateSlider.sliderReleased.connect(self.hikFrameRateSliderReleased)
        # IR
        self.homeInterface.guideInterface.guideLoadButton.toggled.connect(lambda checked: self.guideLoadButtonClicked(checked))
        self.homeInterface.guideInterface.guideColorCheckBox.clicked.connect(self.guideColorCheckClicked)
        self.homeInterface.guideInterface.guideColorComboBox.currentIndexChanged.connect(self.guideColorComboChanged)
        self.homeInterface.guideInterface.guideFocalButton.clicked.connect(self.guideFocalButtonClicked)
        self.sigShowIrVideo.connect(self.onShowIrVideo)
        # Store
        self.homeInterface.storeInterface.storeCard.clicked.connect(self.storeCardClicked)
        self.homeInterface.storeInterface.storeRgbCheckBox_1.clicked.connect(self.storeRgbCheckBox_1Changed)
        self.homeInterface.storeInterface.storeIrCheckBox_1.clicked.connect(self.storeIrCheckBox_1Changed)
        self.homeInterface.storeInterface.storeIrCheckBox_2.clicked.connect(self.storeIrCheckBox_2Changed)
        # State
        self.homeInterface.stateStartButton.toggled.connect(lambda checked: self.startButtonClicked(checked))
        self.homeInterface.stateGrabButton.clicked.connect(self.stateGrabButtonClicked)

    # ------------------------------------------------------------------
    # RGB 相机处理
    # ------------------------------------------------------------------
    def hikEnumButtonClicked(self):
        """遍历可用 RGB 设备并刷新下拉列表。"""
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

    def hikOpenButtonClicked(self, checked):
        """开关 RGB 相机。

        Parameters
        ----------
        checked : bool
            True 表示按钮当前为“关闭设备”状态(准备执行关机)；False 表示准备开机。
        """
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
        """增益滑条释放：写入驱动并刷新状态。"""
        value = self.homeInterface.hikInterface.hikGainSlider.value()
        self.rgbDriver.param.set_gain(value)
        self.rgbDriver.hk_set_param()
        self.stateDisplay()

    def hikExposeSliderReleased(self):
        """曝光时间滑条释放：写入驱动并刷新状态。"""
        value = self.homeInterface.hikInterface.hikExposeSlider.value()
        self.rgbDriver.param.set_exposure_time(value)
        self.rgbDriver.hk_set_param()
        self.stateDisplay()

    def hikFrameRateSliderReleased(self):
        """帧率滑条释放：写入驱动并刷新状态。"""
        value = self.homeInterface.hikInterface.hikFrameRateSlider.value()
        self.rgbDriver.param.set_frame_rate(value)
        self.rgbDriver.hk_set_param()
        self.stateDisplay()

    # ------------------------------------------------------------------
    # IR 相机处理
    # ------------------------------------------------------------------
    def guideLoadButtonClicked(self, checked):
        """登录/登出 IR 相机。"""
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
        """开关色带显示。"""
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
        """更换伪彩映射色带。"""
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
        """执行自动调焦。"""
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

    # ------------------------------------------------------------------
    # 视频回调与显示
    # ------------------------------------------------------------------
    def onShowIrVideo(self, image: QImage):
        """在标签上显示 IR 图像。

        若未登录则清空。

        Parameters
        ----------
        image : QImage
            回调转换后的 RGB 图像。
        """
        if self.irDriver._logged_in:
            self.homeInterface.irLabel.setPixmap(QPixmap.fromImage(image))
        else:
            self.homeInterface.irLabel.clear()

    def _on_rtsp(self, outdata, w, h, user):
        """IR RTSP 原始帧回调 (C 回调包装)。

        将裸数据转换为 QImage 并通过信号转发，避免跨线程直接操作 UI。

        Parameters
        ----------
        outdata : bytes/ctypes
            BGR/RGB 缓冲区指针。
        w : int
            宽度。
        h : int
            高度。
        user : Any
            透传用户数据(未使用)。
        """
        try:
            if not outdata or w <= 0 or h <= 0:
                return
            size = int(w) * int(h) * 3
            buf = ct.string_at(outdata, size)
            img = QImage(buf, int(w), int(h), int(w) * 3, QImage.Format_RGB888).copy()
            self.sigShowIrVideo.emit(img)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 存储参数交互
    # ------------------------------------------------------------------
    def storeCardClicked(self):
        """选择存储目录并持久化。"""
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
        """更新是否保存 RGB 图片并写文件。"""
        flag = self.homeInterface.storeInterface.storeRgbCheckBox_1.isChecked()
        self.storeManage.set_save_rgb_img(flag)
        self.initSettings()
        self.storeManage.save_param_to_file(self.paramConfig)

    def storeIrCheckBox_1Changed(self):
        """更新是否保存 IR 伪彩图并写文件。"""
        flag = self.homeInterface.storeInterface.storeIrCheckBox_1.isChecked()
        self.storeManage.set_save_ir_img(flag)
        self.initSettings()
        self.storeManage.save_param_to_file(self.paramConfig)

    def storeIrCheckBox_2Changed(self):
        """更新是否保存 IR 温度矩阵并写文件。"""
        flag = self.homeInterface.storeInterface.storeIrCheckBox_2.isChecked()
        self.storeManage.set_save_ir_temp(flag)
        self.initSettings()
        self.storeManage.save_param_to_file(self.paramConfig)

    # ------------------------------------------------------------------
    # 采样控制 / 抓拍
    # ------------------------------------------------------------------
    def startButtonClicked(self, checked):
        """开始/结束采样。

        Parameters
        ----------
        checked : bool
            True 表示当前按钮显示“结束采样”(即准备执行停止)。
        """
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
        """执行单次抓拍（依据启用的存储选项）。"""
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
        if self.rgbBusyFlag and self.storeManage.save_rgb_img:
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

    # ------------------------------------------------------------------
    # 状态显示与控件使能
    # ------------------------------------------------------------------
    def stateDisplay(self):
        """组合当前状态 Markdown 文本并更新显示。"""
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
        stateBrowserMarkdown += "##### 状态: 已开启 | " if rgbOpen else "##### 状态: 已关闭 | "
        stateBrowserMarkdown += "采样: 进行中\n" if rgbBusy else "采样: 已停止\n"
        if rgbOpen:
            stateBrowserMarkdown += "##### 曝光时间: " + str(exposureTime) + "us\n"
            stateBrowserMarkdown += "##### 增益: " + str(gain) + "\n"
            stateBrowserMarkdown += "##### 帧率: " + str(frameRate) + " fps\n"
        stateBrowserMarkdown += "#### 📹 **IR 相机**: \n"
        stateBrowserMarkdown += "##### 状态: 已开启 | " if irOpen else "##### 状态: 已关闭 | "
        stateBrowserMarkdown += "采样: 进行中\n" if irBusy else "采样: 已停止\n"
        if irOpen:
            stateBrowserMarkdown += "##### 色带: 已开启\n" if irColorUsage else "##### 色带: 已关闭\n"
            stateBrowserMarkdown += "##### 色彩映射编号: " + str(irColorCode) + "\n"
        self.homeInterface.stateTextBrowser.setMarkdown(stateBrowserMarkdown)

    # 下面一组函数仅负责控件启用/禁用，保持精简故不再展开文档。
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
    setTheme(Theme.DARK)
    app = QApplication(sys.argv)
    translator = FluentTranslator()
    app.installTranslator(translator)
    w = Window()
    w.show()
    app.exec_()
