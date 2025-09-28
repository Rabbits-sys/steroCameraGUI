# -- coding: utf-8 --
"""Hikrobot 相机操作封装。

本模块基于底层 SDK (MvCameraControl_class) 提供较高层的状态化操作接口：
打开/关闭设备、设置参数、启动/停止取流、触发采集、后台线程抓图与显示、保存图像等。

异常处理策略：不再抛出 RuntimeError，统一通过返回值(0 为成功，SDK 原始错误码或自定义负错误码为失败)
并使用 logging 记录。调用方（例如上层 IRCamera 类）统一集中处理错误。

自定义错误码(均为负数，不与 SDK 正常错误码冲突)：
-3001: 线程 ID 无效
-3002: PyThreadState_SetAsyncExc 状态异常
-3003: 设备未打开
-3004: 创建句柄失败
-3005: 打开设备失败
-3006: 启动取流失败
-3007: 停止取流失败
-3008: 关闭设备失败
-3009: 获取参数失败
-3010: 设置曝光失败
-3011: 设置增益失败
-3012: 设置帧率失败
-3013: 设置触发模式失败
-3014: 保存 JPG 失败
-3015: 保存 BMP 失败
-3016: 取图超时/无数据
-3017: 调用顺序错误

典型使用流程：
1. 外部枚举设备并构造 CameraOperation.
2. 调用 Open_device 打开。
3. 按需 Set_parameter / Set_trigger_mode。
4. Start_grabbing 启动后台线程抓图并显示。
5. 需要时保存图像 Save_jpg / Save_Bmp。
6. Stop_grabbing，Close_device 释放资源。

线程安全：图像缓冲拷贝与保存使用互斥锁 self.buf_lock 保护。

调用方可使用 cam_error_text 将自定义错误码转换为中文描述。
"""
import logging
import threading
import time
import sys
import inspect
import ctypes
from ctypes import c_bool, c_ubyte, POINTER, cast, byref, sizeof, cdll, memset

sys.path.append("./")

from CameraParams_header import *  # 保留：需要大量 SDK 常量 / 结构体
from MvCameraControl_class import *

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')

CAM_OK = 0
CAM_ERR_INVALID_THREAD_ID = -3001
CAM_ERR_THREAD_STATE_FAIL = -3002
CAM_ERR_NOT_OPEN = -3003
CAM_ERR_CREATE_HANDLE_FAIL = -3004
CAM_ERR_OPEN_DEVICE_FAIL = -3005
CAM_ERR_START_GRAB_FAIL = -3006
CAM_ERR_STOP_GRAB_FAIL = -3007
CAM_ERR_CLOSE_DEVICE_FAIL = -3008
CAM_ERR_GET_PARAM_FAIL = -3009
CAM_ERR_SET_EXPOSURE_FAIL = -3010
CAM_ERR_SET_GAIN_FAIL = -3011
CAM_ERR_SET_FPS_FAIL = -3012
CAM_ERR_TRIGGER_MODE_FAIL = -3013
CAM_ERR_SAVE_JPG_FAIL = -3014
CAM_ERR_SAVE_BMP_FAIL = -3015
CAM_ERR_GET_IMAGE_TIMEOUT = -3016
CAM_ERR_CALL_ORDER = -3017

def cam_error_text(code: int) -> str:
    """自定义错误码转中文说明。

    Parameters
    ----------
    code : int
        错误码（0 或 SDK / 自定义负码）。

    Returns
    -------
    str
        中文描述，未知码返回原值字符串。
    """
    mapping = {
        CAM_OK: '成功',
        CAM_ERR_INVALID_THREAD_ID: '线程 ID 无效',
        CAM_ERR_THREAD_STATE_FAIL: '线程状态修改失败',
        CAM_ERR_NOT_OPEN: '设备未打开',
        CAM_ERR_CREATE_HANDLE_FAIL: '创建句柄失败',
        CAM_ERR_OPEN_DEVICE_FAIL: '打开设备失败',
        CAM_ERR_START_GRAB_FAIL: '启动取流失败',
        CAM_ERR_STOP_GRAB_FAIL: '停止取流失败',
        CAM_ERR_CLOSE_DEVICE_FAIL: '关闭设备失败',
        CAM_ERR_GET_PARAM_FAIL: '获取参数失败',
        CAM_ERR_SET_EXPOSURE_FAIL: '设置曝光失败',
        CAM_ERR_SET_GAIN_FAIL: '设置增益失败',
        CAM_ERR_SET_FPS_FAIL: '设置帧率失败',
        CAM_ERR_TRIGGER_MODE_FAIL: '设置触发模式失败',
        CAM_ERR_SAVE_JPG_FAIL: '保存 JPG 失败',
        CAM_ERR_SAVE_BMP_FAIL: '保存 BMP 失败',
        CAM_ERR_GET_IMAGE_TIMEOUT: '取图超时/无数据',
        CAM_ERR_CALL_ORDER: '调用顺序错误',
    }
    return mapping.get(code, f'未知错误码({code})')


def Async_raise(tid, exctype):
    """异步向指定线程抛出异常（危险操作，慎用）。

    一般用于强制结束取流线程，内部通过 PyThreadState_SetAsyncExc 注入 SystemExit。

    Parameters
    ----------
    tid : int
        目标线程 ident。
    exctype : type | BaseException
        异常类型或实例，通常为 SystemExit。

    Returns
    -------
    int
        0(CAM_OK) 成功，负值为自定义错误码。
    """
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        logger.error("Async_raise 失败: 无效线程 id=%s", tid.value)
        return CAM_ERR_INVALID_THREAD_ID
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        logger.error("Async_raise 失败: PyThreadState_SetAsyncExc 返回=%s", res)
        return CAM_ERR_THREAD_STATE_FAIL
    return CAM_OK


def Stop_thread(thread):
    """请求结束线程（内部调用 Async_raise 注入 SystemExit）。

    Parameters
    ----------
    thread : threading.Thread | None
        线程对象。

    Returns
    -------
    int
        成功返回 CAM_OK，失败返回自定义错误码。
    """
    if thread is None:
        return CAM_ERR_INVALID_THREAD_ID
    return Async_raise(thread.ident, SystemExit)


def To_hex_str(num):
    """十进制整数转小写十六进制字符串（无 0x 前缀）。

    Parameters
    ----------
    num : int
        输入整数，可为负（按 32 位补码处理）。

    Returns
    -------
    str
        十六进制表示。
    """
    chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hexStr = ""
    if num < 0:
        num = num + 2 ** 32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr
    return hexStr


def Is_mono_data(enGvspPixelType):
    """判定像素格式是否为黑白（Mono）格式。"""
    if PixelType_Gvsp_Mono8 == enGvspPixelType or PixelType_Gvsp_Mono10 == enGvspPixelType \
            or PixelType_Gvsp_Mono10_Packed == enGvspPixelType or PixelType_Gvsp_Mono12 == enGvspPixelType \
            or PixelType_Gvsp_Mono12_Packed == enGvspPixelType:
        return True
    else:
        return False


def Is_color_data(enGvspPixelType):
    """判定像素格式是否为彩色（Bayer / YUV）格式。"""
    if PixelType_Gvsp_BayerGR8 == enGvspPixelType or PixelType_Gvsp_BayerRG8 == enGvspPixelType \
            or PixelType_Gvsp_BayerGB8 == enGvspPixelType or PixelType_Gvsp_BayerBG8 == enGvspPixelType \
            or PixelType_Gvsp_BayerGR10 == enGvspPixelType or PixelType_Gvsp_BayerRG10 == enGvspPixelType \
            or PixelType_Gvsp_BayerGB10 == enGvspPixelType or PixelType_Gvsp_BayerBG10 == enGvspPixelType \
            or PixelType_Gvsp_BayerGR12 == enGvspPixelType or PixelType_Gvsp_BayerRG12 == enGvspPixelType \
            or PixelType_Gvsp_BayerGB12 == enGvspPixelType or PixelType_Gvsp_BayerBG12 == enGvspPixelType \
            or PixelType_Gvsp_BayerGR10_Packed == enGvspPixelType or PixelType_Gvsp_BayerRG10_Packed == enGvspPixelType \
            or PixelType_Gvsp_BayerGB10_Packed == enGvspPixelType or PixelType_Gvsp_BayerBG10_Packed == enGvspPixelType \
            or PixelType_Gvsp_BayerGR12_Packed == enGvspPixelType or PixelType_Gvsp_BayerRG12_Packed == enGvspPixelType \
            or PixelType_Gvsp_BayerGB12_Packed == enGvspPixelType or PixelType_Gvsp_BayerBG12_Packed == enGvspPixelType \
            or PixelType_Gvsp_YUV422_Packed == enGvspPixelType or PixelType_Gvsp_YUV422_YUYV_Packed == enGvspPixelType:
        return True
    else:
        return False


class CameraOperation:
    """相机操作封装类（负责设备生命周期与图像抓取）。

    负责：创建/打开/关闭、启动/停止取流、参数读写、触发、后台线程抓图、图像保存。
    所有方法以整数返回值指示结果（0 成功，非 0 失败）。
    """

    def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False, b_start_grabbing=False,
                 h_thread_handle=None,
                 b_thread_closed=False, st_frame_info=None, b_exit=False, b_save_bmp=False, b_save_jpg=False,
                 buf_save_image=None,
                 n_save_image_size=0, n_win_gui_id=0, frame_rate=0, exposure_time=0, gain=0):
        self.obj_cam = obj_cam
        self.st_device_list = st_device_list
        self.n_connect_num = n_connect_num
        self.b_open_device = b_open_device
        self.b_start_grabbing = b_start_grabbing
        self.b_thread_closed = b_thread_closed
        self.st_frame_info = st_frame_info
        self.b_exit = b_exit
        self.b_save_bmp = b_save_bmp
        self.b_save_jpg = b_save_jpg
        self.buf_save_image = buf_save_image
        self.n_save_image_size = n_save_image_size
        self.h_thread_handle = h_thread_handle
        self.frame_rate = frame_rate
        self.exposure_time = exposure_time
        self.gain = gain
        self.buf_lock = threading.Lock()

    def Open_device(self):
        """打开相机设备并做基础配置。

        Returns
        -------
        int
            0 成功；失败返回 SDK 错误码或 MV_E_CALLORDER。
        """
        if not self.b_open_device:
            if self.n_connect_num < 0:
                return MV_E_CALLORDER
            nConnectionNum = int(self.n_connect_num)
            stDeviceList = cast(self.st_device_list.pDeviceInfo[int(nConnectionNum)],
                                POINTER(MV_CC_DEVICE_INFO)).contents
            self.obj_cam = MvCamera()
            ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
            if ret != 0:
                self.obj_cam.MV_CC_DestroyHandle()
                return ret
            ret = self.obj_cam.MV_CC_OpenDevice()
            if ret != 0:
                return ret
            print("open device successfully!")
            self.b_open_device = True
            self.b_thread_closed = False
            if stDeviceList.nTLayerType == MV_GIGE_DEVICE or stDeviceList.nTLayerType == MV_GENTL_GIGE_DEVICE:
                nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
                if int(nPacketSize) > 0:
                    ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                    if ret != 0:
                        print("warning: set packet size fail! ret[0x%x]" % ret)
                else:
                    print("warning: set packet size fail! ret[0x%x]" % nPacketSize)
            stBool = c_bool(False)
            ret = self.obj_cam.MV_CC_GetBoolValue("AcquisitionFrameRateEnable", stBool)
            if ret != 0:
                print("get acquisition frame rate enable fail! ret[0x%x]" % ret)
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            if ret != 0:
                print("set trigger mode fail! ret[0x%x]" % ret)
            return MV_OK

    def Start_grabbing(self, winHandle):
        """启动取流并开启后台线程抓取显示。

        Parameters
        ----------
        winHandle : int
            窗口句柄（显示接口使用）。

        Returns
        -------
        int
            0 成功；失败返回 SDK 错误码；若未打开或已在取流返回 MV_E_CALLORDER。
        """
        if not self.b_start_grabbing and self.b_open_device:
            self.b_exit = False
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                return ret
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            try:
                self.h_thread_handle = threading.Thread(target=CameraOperation.Work_thread, args=(self, winHandle))
                self.h_thread_handle.start()
                self.b_thread_closed = True
            finally:
                pass
            return MV_OK
        return MV_E_CALLORDER

    def Stop_grabbing(self):
        """停止取流并结束后台线程。"""
        if self.b_start_grabbing and self.b_open_device:
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_StopGrabbing()
            if ret != 0:
                return ret
            print("stop grabbing successfully!")
            self.b_start_grabbing = False
            self.b_exit = True
            return MV_OK
        else:
            return MV_E_CALLORDER

    def Close_device(self):
        """关闭相机并销毁句柄。"""
        if self.b_open_device:
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                return ret
        self.obj_cam.MV_CC_DestroyHandle()
        self.b_open_device = False
        self.b_start_grabbing = False
        self.b_exit = True
        print("close device successfully!")
        return MV_OK

    def Set_trigger_mode(self, is_trigger_mode):
        """设置触发模式（连续或软触发）。

        Parameters
        ----------
        is_trigger_mode : bool
            True 设为软触发；False 关闭触发（连续采集）。

        Returns
        -------
        int
            0 成功；失败返回 SDK 错误码；未打开返回 MV_E_CALLORDER。
        """
        if not self.b_open_device:
            return MV_E_CALLORDER
        if not is_trigger_mode:
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 0)
            if ret != 0:
                return ret
        else:
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 1)
            if ret != 0:
                return ret
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", 7)
            if ret != 0:
                return ret
        return MV_OK

    def Trigger_once(self):
        """执行一次软触发（触发模式已开启时有效）。"""
        if self.b_open_device:
            return self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")

    def Get_parameter(self):
        """读取帧率/曝光/增益并缓存到属性。"""
        if self.b_open_device:
            stFloatParam_FrameRate = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_FrameRate), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_exposureTime = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_exposureTime), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_gain = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_gain), 0, sizeof(MVCC_FLOATVALUE))
            ret = self.obj_cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stFloatParam_FrameRate)
            if ret != 0:
                return ret
            self.frame_rate = stFloatParam_FrameRate.fCurValue
            ret = self.obj_cam.MV_CC_GetFloatValue("ExposureTime", stFloatParam_exposureTime)
            if ret != 0:
                return ret
            self.exposure_time = stFloatParam_exposureTime.fCurValue
            ret = self.obj_cam.MV_CC_GetFloatValue("Gain", stFloatParam_gain)
            if ret != 0:
                return ret
            self.gain = stFloatParam_gain.fCurValue
            return MV_OK

    def Set_parameter(self, frameRate, exposureTime, gain):
        """设置帧率/曝光/增益。参数字符串会自动转 float。"""
        if '' == frameRate or '' == exposureTime or '' == gain:
            print('show info', 'please type in the text box !')
            return MV_E_PARAMETER
        if self.b_open_device:
            ret = self.obj_cam.MV_CC_SetEnumValue("ExposureAuto", 0)
            time.sleep(0.2)
            ret = self.obj_cam.MV_CC_SetFloatValue("ExposureTime", float(exposureTime))
            if ret != 0:
                print('show error', 'set exposure time fail! ret = ' + To_hex_str(ret))
                return ret
            ret = self.obj_cam.MV_CC_SetFloatValue("Gain", float(gain))
            if ret != 0:
                print('show error', 'set gain fail! ret = ' + To_hex_str(ret))
                return ret
            ret = self.obj_cam.MV_CC_SetFloatValue("AcquisitionFrameRate", float(frameRate))
            if ret != 0:
                print('show error', 'set acquistion frame rate fail! ret = ' + To_hex_str(ret))
                return ret
            print('show info', 'set parameter success!')
            return MV_OK

    def Work_thread(self, winHandle):
        """取流线程：循环获取图像、拷贝、显示，直到 b_exit 为 True。"""
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))
        while True:
            ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
            if 0 == ret:
                if self.buf_save_image is None:
                    self.buf_save_image = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
                self.st_frame_info = stOutFrame.stFrameInfo
                self.buf_lock.acquire()
                cdll.msvcrt.memcpy(byref(self.buf_save_image), stOutFrame.pBufAddr, self.st_frame_info.nFrameLen)
                self.buf_lock.release()
                print("get one frame: Width[%d], Height[%d], nFrameNum[%d]" % (self.st_frame_info.nWidth, self.st_frame_info.nHeight, self.st_frame_info.nFrameNum))
                self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
            else:
                print("no data, ret = " + To_hex_str(ret))
                continue
            stDisplayParam = MV_DISPLAY_FRAME_INFO()
            memset(byref(stDisplayParam), 0, sizeof(stDisplayParam))
            stDisplayParam.hWnd = int(winHandle)
            stDisplayParam.nWidth = self.st_frame_info.nWidth
            stDisplayParam.nHeight = self.st_frame_info.nHeight
            stDisplayParam.enPixelType = self.st_frame_info.enPixelType
            stDisplayParam.pData = self.buf_save_image
            stDisplayParam.nDataLen = self.st_frame_info.nFrameLen
            self.obj_cam.MV_CC_DisplayOneFrame(stDisplayParam)
            if self.b_exit:
                if self.buf_save_image is not None:
                    del self.buf_save_image
                break

    def Save_jpg(self):
        """保存最新帧为 JPG（文件名=帧号.jpg）。"""
        if self.buf_save_image is None:
            return
        self.buf_lock.acquire()
        file_path = str(self.st_frame_info.nFrameNum) + ".jpg"
        c_file_path = file_path.encode('ascii')
        stSaveParam = MV_SAVE_IMAGE_TO_FILE_PARAM_EX()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType
        stSaveParam.nWidth = self.st_frame_info.nWidth
        stSaveParam.nHeight = self.st_frame_info.nHeight
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Jpeg
        stSaveParam.nQuality = 80
        stSaveParam.pcImagePath = ctypes.create_string_buffer(c_file_path)
        stSaveParam.iMethodValue = 1
        ret = self.obj_cam.MV_CC_SaveImageToFileEx(stSaveParam)
        self.buf_lock.release()
        return ret

    def Save_Bmp(self):
        """保存最新帧为 BMP（文件名=帧号.bmp）。"""
        if 0 == self.buf_save_image:
            return
        self.buf_lock.acquire()
        file_path = str(self.st_frame_info.nFrameNum) + ".bmp"
        c_file_path = file_path.encode('ascii')
        stSaveParam = MV_SAVE_IMAGE_TO_FILE_PARAM_EX()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType
        stSaveParam.nWidth = self.st_frame_info.nWidth
        stSaveParam.nHeight = self.st_frame_info.nHeight
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Bmp
        stSaveParam.pcImagePath = ctypes.create_string_buffer(c_file_path)
        stSaveParam.iMethodValue = 1
        ret = self.obj_cam.MV_CC_SaveImageToFileEx(stSaveParam)
        self.buf_lock.release()
        return ret
