"""海康可见光相机封装模块。

提供设备枚举、打开/关闭、取流控制、参数获取与设置、图像保存等功能的轻量级封装。

Notes
-----
- 所有以 ``hk_`` 前缀的方法均返回 ``MV_OK`` 表示成功，返回 ``not MV_OK`` 表示失败。
- 失败时记录日志，不抛出异常（保持与原始用法兼容）。
- 部分底层 SDK 全局函数及常量来自 `driver.hikrobot` 目录。
"""
import ctypes as ct
import logging
from typing import Optional

from driver.hikrobot.CamOperation_class import CameraOperation, To_hex_str
from driver.hikrobot.MvCameraControl_class import *  # noqa: F401,F403
from driver.hikrobot.MvErrorDefine_const import *     # noqa: F401,F403
from driver.hikrobot.CameraParams_header import *     # noqa: F401,F403

logger = logging.getLogger(__name__)

def decoding_char(c_ubyte_value):
    """将底层 SDK 返回的无符号字节指针转换为 Python 字符串。

    支持 GBK 解码，若失败则退化为原始 `bytes` 字符串表示。

    Parameters
    ----------
    c_ubyte_value : POINTER(c_ubyte) | c_char_p
        底层返回的指针。

    Returns
    -------
    str
        解码后的字符串。
    """
    c_char_p_value = ct.cast(c_ubyte_value, ct.c_char_p)
    try:
        decode_str = c_char_p_value.value.decode('gbk')
    except UnicodeDecodeError:
        decode_str = str(c_char_p_value.value)
    return decode_str

class RGBCamera(object):
    """海康可见光（RGB）相机操作封装。

    封装设备枚举、打开/关闭、开始/停止取流、参数查询/设置、保存图片等典型操作。

    Attributes
    ----------
    param : RGBCameraParam
        相机运行参数（曝光、增益、帧率）。
    hk_deviceList : MV_CC_DEVICE_INFO_LIST
        设备信息列表结构体。
    hk_cam : MvCamera
        底层相机对象实例。
    hk_nSelCamIndex : int
        当前选中设备索引。
    hk_obj_cam_operation : CameraOperation | None
        高层操作对象（打开设备后创建）。
    logged_in : bool
        设备是否已打开（对应底层句柄已建立）。
    video_opened : bool
        是否处于取流状态。
    """
    def __init__(self):
        self.param = RGBCameraParam()
        MvCamera.MV_CC_Initialize()
        self.hk_deviceList = MV_CC_DEVICE_INFO_LIST()
        self.hk_cam = MvCamera()
        self.hk_nSelCamIndex = 0
        self.hk_obj_cam_operation: Optional[CameraOperation] = None
        self.logged_in = False
        self.video_opened = False

    def __del__(self):
        try:
            if self.video_opened:
                self.hk_stop_grabbing()
            if self.logged_in:
                self.hk_close_device()
        except Exception:
            pass

    def hk_enum_devices(self):
        """枚举可用相机设备。

        Returns
        -------
        tuple[int, list[str] | None]
            (错误码, 设备描述列表)。失败或无设备时列表为 ``None``。
        """
        self.hk_deviceList = MV_CC_DEVICE_INFO_LIST()
        n_layer_type = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                        | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
        ret = MvCamera.MV_CC_EnumDevices(n_layer_type, self.hk_deviceList)
        if ret != MV_OK:
            logger.error("Enumerate device list failed: %s", To_hex_str(ret))
            return not MV_OK, None
        if self.hk_deviceList.nDeviceNum == 0:
            logger.warning("No device found")
            return not MV_OK, None
        logger.info('Found %d device(s)', self.hk_deviceList.nDeviceNum)
        devList = []
        for i in range(0, self.hk_deviceList.nDeviceNum):
            mvcc_dev_info = cast(self.hk_deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE:
                logger.debug("gige device: [%d]", i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                devList.append(f"[{i}]GigE: {user_defined_name} {model_name}({nip1}.{nip2}.{nip3}.{nip4})")
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                logger.debug("u3v device: [%d]", i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName)
                logger.debug("device user define name: %s", user_defined_name)
                logger.debug("device model name: %s", model_name)

                sn_chars = []
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    sn_chars.append(chr(per))
                logger.debug("user serial number: %s", ''.join(sn_chars))
                devList.append(f"[{i}]USB: {user_defined_name} {model_name}({''.join(sn_chars)})")
            elif mvcc_dev_info.nTLayerType == MV_GENTL_CAMERALINK_DEVICE:
                logger.debug("CML device: [%d]", i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chModelName)
                logger.debug("device user define name: %s", user_defined_name)
                logger.debug("device model name: %s", model_name)

                sn_chars = []
                for per in mvcc_dev_info.SpecialInfo.stCMLInfo.chSerialNumber:
                    if per == 0:
                        break
                    sn_chars.append(chr(per))
                logger.debug("user serial number: %s", ''.join(sn_chars))
                devList.append(f"[{i}]CML: {user_defined_name} {model_name}({''.join(sn_chars)})")
            elif mvcc_dev_info.nTLayerType == MV_GENTL_CXP_DEVICE:
                logger.debug("CXP device: [%d]", i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chModelName)
                logger.debug("device user define name: %s", user_defined_name)
                logger.debug("device model name: ", model_name)

                sn_chars = []
                for per in mvcc_dev_info.SpecialInfo.stCXPInfo.chSerialNumber:
                    if per == 0:
                        break
                    sn_chars.append(chr(per))
                logger.debug("user serial number: %s", ''.join(sn_chars))
                devList.append(f"[{i}]CXP: {user_defined_name} {model_name}({''.join(sn_chars)})")
            elif mvcc_dev_info.nTLayerType == MV_GENTL_XOF_DEVICE:
                logger.debug("XoF device: [%d]", i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chModelName)
                logger.debug("device user define name: %s", user_defined_name)
                logger.debug("device model name: %s", model_name)

                sn_chars = []
                for per in mvcc_dev_info.SpecialInfo.stXoFInfo.chSerialNumber:
                    if per == 0:
                        break
                    sn_chars.append(chr(per))
                logger.debug("user serial number: %s", ''.join(sn_chars))
                devList.append(f"[{i}]XoF: {user_defined_name} {model_name}({''.join(sn_chars)})")
        return MV_OK, devList

    def hk_open_device(self, nSelCamIndex: int):
        """打开指定索引的设备。

        Parameters
        ----------
        nSelCamIndex : int
            设备列表索引（来自 :meth:`hk_enum_devices`）。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码（以 ``not MV_OK`` 表示）。
        """
        if self.logged_in:
            logger.warning("Already logged in")
            return not MV_OK
        if nSelCamIndex < 0:
            logger.error("Open device failed: no device selected")
            return not MV_OK
        self.hk_obj_cam_operation = CameraOperation(self.hk_cam, self.hk_deviceList, nSelCamIndex)
        ret = self.hk_obj_cam_operation.Open_device()
        if ret != MV_OK:
            logger.error("Open device failed: %s", To_hex_str(ret))
            self.logged_in = False
            return not MV_OK
        self.hk_set_continue_mode()
        self.logged_in = True
        logger.info('Open device succeeded')
        return MV_OK

    def hk_start_grabbing(self, ui_id):
        """开始取流。

        Parameters
        ----------
        ui_id : int
            用于显示的窗口句柄（winId）。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码。
        """
        if not self.logged_in:
            logger.error("Start grabbing failed: not logged in")
            return not MV_OK
        if self.video_opened:
            logger.warning("Already started grabbing")
            return MV_OK
        ret = self.hk_obj_cam_operation.Start_grabbing(ui_id)
        if ret != 0:
            logger.error("Start grabbing failed: %s", To_hex_str(ret))
            return not MV_OK
        self.video_opened = True
        logger.info('Start grabbing succeeded')
        return MV_OK

    def hk_stop_grabbing(self):
        """停止取流。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码。
        """
        ret = self.hk_obj_cam_operation.Stop_grabbing()
        self.video_opened = False
        if ret != MV_OK:
            logger.error("Stop grabbing failed: %s", To_hex_str(ret))
            return not MV_OK
        logger.info('Stop grabbing succeeded')
        return MV_OK

    def hk_close_device(self):
        """关闭设备（若正在取流会先停止）。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码。
        """
        if not self.logged_in:
            logger.warning("Already logged out")
            return MV_OK
        self.hk_stop_grabbing()
        self.video_opened = False
        self.hk_obj_cam_operation.Close_device()
        self.logged_in = False
        logger.info('Logged out succeeded')
        return MV_OK

    def hk_set_continue_mode(self):
        """设置为连续取流模式。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码。
        """
        ret = self.hk_obj_cam_operation.Set_trigger_mode(False)
        if ret != MV_OK:
            logger.error("Set trigger mode failed: %s", To_hex_str(ret))
            return not MV_OK
        logger.info('Set trigger mode succeeded')
        return MV_OK

    def hk_save_jpg(self, file_path):
        """保存当前帧为 JPG 文件。

        文件名采用当前时间戳 ``YYYYMMDDHHMMSS.jpg``。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码。
        """
        ret = self.hk_obj_cam_operation.Save_jpg(file_path)
        if ret != MV_OK:
            logger.error("Save jpg failed: %s", To_hex_str(ret))
            return not MV_OK
        logger.info('Save jpg succeeded: %s', file_path)
        return MV_OK

    def hk_get_param(self):
        """读取相机运行参数并更新内部缓存。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码。
        """
        ret = self.hk_obj_cam_operation.Get_parameter()
        if ret != MV_OK:
            logger.error("Get param failed: %s", To_hex_str(ret))
            return not MV_OK
        self.param.exposure_time = self.hk_obj_cam_operation.exposure_time
        self.param.gain = self.hk_obj_cam_operation.gain
        self.param.frame_rate = self.hk_obj_cam_operation.frame_rate
        logger.info('Get param succeeded: exposure_time=%s, gain=%s, frame_rate=%s',str(self.param.exposure_time),str(self.param.gain),str(self.param.frame_rate))
        return MV_OK

    def hk_set_param(self):
        """向设备写入当前缓存的曝光/增益/帧率参数。

        Returns
        -------
        int
            ``MV_OK`` 成功；失败返回错误码。
        """
        frame_rate = str(self.param.frame_rate)
        exposure_time = str(self.param.exposure_time)
        gain = str(self.param.gain)
        ret = self.hk_obj_cam_operation.Set_parameter(frame_rate, exposure_time, gain)
        if ret != MV_OK:
            logger.error("Set param failed: %s", To_hex_str(ret))
            return not MV_OK
        logger.info('Set param succeeded')
        return MV_OK

class RGBCameraParam(object):
    """RGB 相机参数容器。

    保存并校验曝光时间 / 增益 / 帧率配置。

    Attributes
    ----------
    exposure_time : int
        曝光时间 (μs)，默认 20000，合法范围 [1000, 1_000_000]。
    gain : int
        模拟增益 (dB)，默认 0，合法范围 [0, 17]。
    frame_rate : float
        帧率 (fps)，默认 30.0，合法范围 [0.1, 60.0]。
    """
    def __init__(self):
        self.exposure_time = -1
        self.gain = -1
        self.frame_rate = -1

    def reset_param(self):
        self.exposure_time = -1
        self.gain = -1
        self.frame_rate = -1

    def set_exposure_time(self, exposure_time: int):
        """设置曝光时间。

        规则：15 ≤ 曝光时间 ≤ 20000。

        Parameters
        ----------
        exposure_time : int
            曝光时间，单位微秒。

        Returns
        -------
        int
            ``MV_OK`` 成功；非法返回错误码。
        """
        if not isinstance(exposure_time, int) or not (15 <= exposure_time <= 20000):
            logger.error("Set exposure time failed: illegal parameter")
            return not MV_OK
        self.exposure_time = exposure_time
        logger.info("Set exposure time successes: %d", exposure_time)
        return MV_OK

    def set_gain(self, gain: int):
        """设置增益。

        规则：0 ≤ 增益 ≤ 17。

        Parameters
        ----------
        gain : int
            增益，单位 dB。

        Returns
        -------
        int
            ``MV_OK`` 成功；非法返回错误码。
        """
        if not isinstance(gain, int) or not (0 <= gain <= 17):
            logger.error("Set gain failed: illegal parameter")
            return not MV_OK
        self.gain = gain
        logger.info("Set gain successes: %d", gain)
        return MV_OK

    def set_frame_rate(self, frame_rate: float):
        """设置帧率。

        规则：0.1 ≤ 帧率 ≤ 80.0。

        Parameters
        ----------
        frame_rate : float
            帧率，单位 fps。

        Returns
        -------
        int
            ``MV_OK`` 成功；非法返回错误码。
        """
        if not isinstance(frame_rate, float) or not (0.1 <= frame_rate <= 80.0):
            logger.error("Set frame rate failed: illegal parameter")
            return not MV_OK
        self.frame_rate = float(frame_rate)
        logger.info("Set frame rate successes: %.2f", frame_rate)
        return MV_OK
