"""IR 红外相机底层封装及面向对象接口。

本文件分两层：
1. 底层轻量 C 接口包装（直接映射 DLL 函数），函数命名与 DLL 一致或语义化；不做复杂检查。
2. IRCamera 类：提供句柄管理、登录/注销、视频打开/关闭、录像、抓图、热力图、温度矩阵、测温参数、
   快门、对焦、重启等一站式功能，并统一 error code 与日志。所有方法通过返回整型错误码或 (错误码, 数据) 形式。

错误处理策略：
- 底层 init/login 等直接返回 SDK 整型返回值，不抛出 RuntimeError。
- IRCamera 内部把 SDK 返回值映射为自定义错误码 (SGP_ERR_*)，并记录 last_error、last_vendor_code。
- 0 表示成功 (SGP_OK)，负值为自定义错误码。

主要自定义错误码：
-1001: 设备未初始化
-1002: 初始化失败
-1100: 登录失败
-1200: 打开视频失败
-1300: 开始录像失败
-1400: 抓图失败
-1500: 热力图获取失败
-1600: 温度矩阵获取失败
-1700: 通用信息获取失败
-1710: 版本信息获取失败
-1800: 读测温参数失败
-1810: 写测温参数失败
-1900: 快门操作失败
-1910: 对焦失败
-2000: 重启失败

快速示例（示意）：
1. 创建并登录: cam = IRCamera('192.168.1.64','admin','12345'); cam.login()
2. 获取信息: ret, info = cam.get_general_info()
3. 打开视频: cam.open_ir_video(lambda data,w,h,user: None)
4. 关闭与释放: cam.close_ir_video(); cam.logout(); cam.release()

线程安全：
- DLL 回调需要保持 Python 回调对象引用 (self._video_callback, self._record_callback)。
- 录像类型集合用于跟踪已启动的多路录像。

注意：
- 模块加载时会尝试定位 SgpApi.dll；未找到将抛出 FileNotFoundError（初始化前即失败）。
- 若需静默处理，可在上层捕获并转换为自定义错误码。
"""
import os
import ctypes as ct
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')

STRING_LENGH = 50
RANGE_MAX_NUM = 3
SGP_OK = 0
SGP_ERR_NOT_INITIALIZED = -1001
SGP_ERR_INIT_FAILED = -1002
SGP_ERR_LOGIN_FAILED = -1100
SGP_ERR_OPEN_VIDEO_FAILED = -1200
SGP_ERR_RECORD_START_FAILED = -1300
SGP_ERR_CAPTURE_FAILED = -1400
SGP_ERR_HEATMAP_FAILED = -1500
SGP_ERR_GET_TEMPS_FAILED = -1600
SGP_ERR_GET_GENERAL_FAILED = -1700
SGP_ERR_GET_VERSION_FAILED = -1710
SGP_ERR_GET_THERM_PARAM_FAILED = -1800
SGP_ERR_SET_THERM_PARAM_FAILED = -1810
SGP_ERR_SHUTTER_FAILED = -1900
SGP_ERR_FOCUS_FAILED = -1910
SGP_ERR_REBOOT_FAILED = -2000

SGP_VL_IMAGE = 1
SGP_IR_IMAGE = 2
SGP_VL_VIDEO = 1
SGP_IR_VIDEO = 2
SGP_SHUTTER = 1
SGP_FOCUS_AUTO = 5

SGP_HANDLE = ct.c_ulonglong

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if hasattr(os, 'add_dll_directory'):
    try:
        os.add_dll_directory(_ROOT_DIR)
    except FileNotFoundError:
        pass

_DLL_PATH = os.path.join(_ROOT_DIR, 'SgpApi.dll')
if not os.path.isfile(_DLL_PATH):
    raise FileNotFoundError('SgpApi.dll not found at: %s' % _DLL_PATH)

_lib = ct.CDLL(_DLL_PATH)

class SGP_RANGE(ct.Structure):
    """测温量程结构。

    属性
    ----
    - min (int): 最小温度。
    - max (int): 最大温度。
    """
    _fields_ = [('min', ct.c_int), ('max', ct.c_int)]

class SGP_GENERAL_INFO(ct.Structure):
    """通用信息结构, 包含时间、RTSP URL、分辨率与量程等。"""
    _fields_ = [
        ('datetime', ct.c_char * STRING_LENGH),
        ('ir_rtsp_url', ct.c_char * STRING_LENGH),
        ('ir_sub_rtsp_url', ct.c_char * STRING_LENGH),
        ('ir_model_w', ct.c_int),
        ('ir_model_h', ct.c_int),
        ('ir_output_w', ct.c_int),
        ('ir_output_h', ct.c_int),
        ('range_num', ct.c_int),
        ('range', SGP_RANGE * RANGE_MAX_NUM),
        ('vl_rtsp_url', ct.c_char * STRING_LENGH),
        ('vl_sub_rtsp_url', ct.c_char * STRING_LENGH),
    ]

class SGP_VERSION_INFO(ct.Structure):
    """版本信息结构(型号/版本号/序列号/FPGA 等)。"""
    _fields_ = [
        ('model', ct.c_char * STRING_LENGH),
        ('version', ct.c_char * STRING_LENGH),
        ('serial', ct.c_char * STRING_LENGH),
        ('fpga_version', ct.c_char * STRING_LENGH),
        ('measure_version', ct.c_char * STRING_LENGH),
        ('sdk_version', ct.c_char * STRING_LENGH),
    ]

class SGP_THERMOMETRY_PARAM(ct.Structure):
    """测温参数结构。包含调色板、显示模式、距离、发射率、环境温度等。"""
    _fields_ = [
        ('color_bar', ct.c_int), ('color_show', ct.c_int), ('flag', ct.c_int),
        ('mod_temp', ct.c_float), ('show_mode', ct.c_int), ('gear', ct.c_int),
        ('show_string', ct.c_int), ('show_desc', ct.c_char * STRING_LENGH),
        ('atmo_trans', ct.c_float), ('dist', ct.c_float), ('emiss', ct.c_float),
        ('emiss_mode', ct.c_int), ('humi', ct.c_int), ('opti_trans', ct.c_float),
        ('ref_temp', ct.c_float), ('isot_flag', ct.c_int), ('isot_high', ct.c_float),
        ('isot_high_color', ct.c_char * STRING_LENGH), ('isot_low', ct.c_int),
        ('isot_low_color', ct.c_char * STRING_LENGH), ('isot_type', ct.c_int),
        ('ambient', ct.c_float),
    ]

SGP_RTSPCALLBACK = ct.CFUNCTYPE(None, ct.POINTER(ct.c_ubyte), ct.c_int, ct.c_int, ct.c_void_p)
SGP_RECORDCALLBACK = ct.CFUNCTYPE(None, ct.c_int, ct.c_void_p)

_lib.SGP_InitDevice.restype = SGP_HANDLE
_lib.SGP_UnInitDevice.argtypes = [SGP_HANDLE]
_lib.SGP_UnInitDevice.restype = None
_lib.SGP_Login.argtypes = [SGP_HANDLE, ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_int]
_lib.SGP_Login.restype = ct.c_int
_lib.SGP_Logout.argtypes = [SGP_HANDLE]
_lib.SGP_Logout.restype = ct.c_int
_lib.SGP_GetGeneralInfo.argtypes = [SGP_HANDLE, ct.POINTER(SGP_GENERAL_INFO)]
_lib.SGP_GetGeneralInfo.restype = ct.c_int
_lib.SGP_GetVersionInfo.argtypes = [SGP_HANDLE, ct.POINTER(SGP_VERSION_INFO)]
_lib.SGP_GetVersionInfo.restype = ct.c_int
_lib.SGP_OpenIrVideo.argtypes = [SGP_HANDLE, SGP_RTSPCALLBACK, ct.c_void_p]
_lib.SGP_OpenIrVideo.restype = ct.c_int
_lib.SGP_CloseIrVideo.argtypes = [SGP_HANDLE]
_lib.SGP_CloseIrVideo.restype = None
_lib.SGP_StartRecord.argtypes = [SGP_HANDLE, ct.c_int, ct.c_char_p, SGP_RECORDCALLBACK, ct.c_void_p]
_lib.SGP_StartRecord.restype = ct.c_int
_lib.SGP_StopRecord.argtypes = [SGP_HANDLE, ct.c_int]
_lib.SGP_StopRecord.restype = None
_lib.SGP_GetScreenCapture.argtypes = [SGP_HANDLE, ct.c_int, ct.c_char_p]
_lib.SGP_GetScreenCapture.restype = ct.c_int
_lib.SGP_DoShutter.argtypes = [SGP_HANDLE, ct.c_int]
_lib.SGP_DoShutter.restype = ct.c_int
_lib.SGP_GetHeatMap.argtypes = [SGP_HANDLE, ct.c_char_p]
_lib.SGP_GetHeatMap.restype = ct.c_int
_lib.SGP_GetImageTemps.argtypes = [SGP_HANDLE, ct.POINTER(ct.c_float), ct.c_int, ct.c_int]
_lib.SGP_GetImageTemps.restype = ct.c_int
_lib.SGP_GetThermometryParam.argtypes = [SGP_HANDLE, ct.POINTER(SGP_THERMOMETRY_PARAM)]
_lib.SGP_GetThermometryParam.restype = ct.c_int
_lib.SGP_SetThermometryParam.argtypes = [SGP_HANDLE, SGP_THERMOMETRY_PARAM]
_lib.SGP_SetThermometryParam.restype = ct.c_int
_lib.SGP_RebootSystem.argtypes = [SGP_HANDLE]
_lib.SGP_RebootSystem.restype = ct.c_int
_lib.SGP_SetFocus.argtypes = [SGP_HANDLE, ct.c_int, ct.c_int]
_lib.SGP_SetFocus.restype = ct.c_int

def init_device() -> int:
    """初始化设备，获取句柄。

    Returns
    -------
    int
        非 0: 设备句柄(成功)；0: 失败。
    """
    return int(_lib.SGP_InitDevice())

def uninit_device(handle: int) -> None:
    """反初始化设备，释放资源。

    Parameters
    ----------
    handle : int
        设备句柄。
    """
    _lib.SGP_UnInitDevice(SGP_HANDLE(handle))

def login(handle: int, server: str, username: str, password: str, port: int) -> int:
    """登录设备。

    Returns
    -------
    int
        0 成功，非 0 为底层错误码。
    """
    return int(_lib.SGP_Login(SGP_HANDLE(handle), server.encode('utf-8'), username.encode('utf-8'), password.encode('utf-8'), int(port)))

def logout(handle: int) -> int:
    """注销设备。"""
    return int(_lib.SGP_Logout(SGP_HANDLE(handle)))

def get_general_info(handle: int):
    """获取通用信息。

    Returns
    -------
    tuple[int, SGP_GENERAL_INFO]
        (底层返回码, 信息结构)。
    """
    info = SGP_GENERAL_INFO()
    ret = _lib.SGP_GetGeneralInfo(SGP_HANDLE(handle), ct.byref(info))
    return ret, info

def get_version_info(handle: int):
    """获取版本信息。"""
    info = SGP_VERSION_INFO()
    ret = _lib.SGP_GetVersionInfo(SGP_HANDLE(handle), ct.byref(info))
    return ret, info

def open_ir_video(handle: int, callback: SGP_RTSPCALLBACK, user_ptr: ct.c_void_p = None) -> int:
    """开启红外视频流 (RTSP 回调)。"""
    return int(_lib.SGP_OpenIrVideo(SGP_HANDLE(handle), callback, user_ptr))

def close_ir_video(handle: int) -> None:
    """关闭红外视频流。"""
    _lib.SGP_CloseIrVideo(SGP_HANDLE(handle))

def start_record(handle: int, video_type: int, path: str, callback: SGP_RECORDCALLBACK, user_ptr: ct.c_void_p = None) -> int:
    """开始录像。

    Parameters
    ----------
    video_type : int
        录像类型 (SGP_VL_VIDEO / SGP_IR_VIDEO)。
    path : str
        保存路径。
    callback : SGP_RECORDCALLBACK
        录像状态回调。
    """
    return int(_lib.SGP_StartRecord(SGP_HANDLE(handle), int(video_type), path.encode('utf-8'), callback, user_ptr))

def stop_record(handle: int, video_type: int) -> None:
    """停止录像。"""
    _lib.SGP_StopRecord(SGP_HANDLE(handle), int(video_type))

def screen_capture(handle: int, image_type: int, path: str) -> int:
    """抓图保存。"""
    return int(_lib.SGP_GetScreenCapture(SGP_HANDLE(handle), int(image_type), path.encode('utf-8')))

def do_shutter(handle: int, shutter_type: int) -> int:
    """执行快门校正。"""
    return int(_lib.SGP_DoShutter(SGP_HANDLE(handle), int(shutter_type)))

def get_heatmap(handle: int, path: str) -> int:
    """获取热力图并保存。"""
    return int(_lib.SGP_GetHeatMap(SGP_HANDLE(handle), path.encode('utf-8')))

def get_image_temps(handle: int, length: int, mat_type: int = 0):
    """获取温度矩阵。

    Parameters
    ----------
    length : int
        需要读取的温度点个数。
    mat_type : int, default=0
        矩阵类型/模式。

    Returns
    -------
    tuple[int, ctypes.Array]
        (底层返回码, 温度缓冲区)。
    """
    buf = (ct.c_float * length)()
    ret = _lib.SGP_GetImageTemps(SGP_HANDLE(handle), buf, int(length * 4), int(mat_type))
    return ret, buf

def get_thermometry_param(handle: int):
    """读取测温参数。"""
    param = SGP_THERMOMETRY_PARAM()
    ret = _lib.SGP_GetThermometryParam(SGP_HANDLE(handle), ct.byref(param))
    return ret, param

def set_thermometry_param(handle: int, p: SGP_THERMOMETRY_PARAM) -> int:
    """设置测温参数。"""
    return int(_lib.SGP_SetThermometryParam(SGP_HANDLE(handle), p))

def reboot_system(handle: int) -> int:
    """远程重启系统。"""
    return int(_lib.SGP_RebootSystem(SGP_HANDLE(handle)))

def set_focus(handle: int, focus_type: int, value: int = 0) -> int:
    """对焦控制。"""
    return int(_lib.SGP_SetFocus(SGP_HANDLE(handle), int(focus_type), int(value)))

def cstr_to_py(b: bytes) -> str:
    """C char* 字节序列转换为 Python 字符串（尝试 GBK 失败再 UTF-8）。"""
    if not b:
        return ''
    try:
        return b.split(b'\x00', 1)[0].decode('gbk', errors='ignore')
    except Exception:
        return b.split(b'\x00', 1)[0].decode('utf-8', errors='ignore')

class IRCamera:
    """IR 相机高级封装。

    统一管理设备句柄/登录状态/视频流/录像/抓图/热力图/温度矩阵/测温参数/快门/聚焦/重启。

    属性
    ----
    - server (str): 设备地址/IP。
    - username (str): 登录用户名。
    - password (str): 密码。
    - port (int): 端口。
    - handle (int | None): 底层句柄，0/None 表示失效。
    - last_error (int): 最近一次框架层错误码 (自定义)。
    - last_vendor_code (int): 最近一次底层 SDK 原始返回值。
    - _video_opened (bool): 红外视频是否开启。
    - _recording_types (set[int]): 当前正在录像的类型集合。
    """
    def __init__(self, server: str, username: str, password: str, port: int = 80):
        self.server = server
        self.username = username
        self.password = password
        self.port = int(port)
        self.handle: Optional[int] = None
        self._logged_in: bool = False
        self._video_opened: bool = False
        self._video_callback: Optional[Callable] = None
        self._record_callback: Optional[Callable] = None
        self._recording_types: set[int] = set()
        self.last_error: int = SGP_OK
        self.last_vendor_code: int = SGP_OK
        self._init_device()

    def _ensure_handle(self):
        """内部检查句柄是否有效。"""
        if self.handle is None:
            self.last_error = SGP_ERR_NOT_INITIALIZED
            logger.error("IRCamera device handle is None (not initialized)")
            return SGP_ERR_NOT_INITIALIZED
        return SGP_OK

    def _init_device(self):
        """内部初始化设备 (仅首次)。"""
        if self.handle is None:
            self.handle = init_device()
            if not isinstance(self.handle, int) or self.handle == 0:
                self.last_error = SGP_ERR_INIT_FAILED
                self.last_vendor_code = 0
                logger.error("Init device failed, handle=0")

    def __enter__(self):
        """with 上下文进入时自动 login。"""
        self.login()
        return self

    def __exit__(self, exc_type, exc, tb):
        """with 离开时清理资源 (关闭视频 / 停止录像 / 注销 / 释放)。"""
        try:
            self.close_ir_video()
        except Exception:
            pass
        try:
            for t in list(self._recording_types):
                try:
                    self.stop_record(t)
                except Exception:
                    pass
        finally:
            self.logout()
            self.release()
        return False

    def __del__(self):
        """析构：尽力释放资源 (忽略异常)。"""
        try:
            if self._logged_in:
                self.logout()
            self.release()
        except Exception:
            pass

    def login(self):
        """登录设备。已登录则直接成功。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        if self._logged_in:
            return SGP_OK
        ret = login(self.handle, self.server, self.username, self.password, self.port)
        self.last_vendor_code = ret
        if ret == SGP_OK:
            self._logged_in = True
            return SGP_OK
        logger.error("Login failed: %d", ret)
        self.last_error = SGP_ERR_LOGIN_FAILED
        return SGP_ERR_LOGIN_FAILED

    def logout(self):
        """注销登录。未登录时返回成功。"""
        if self.handle is None or not self._logged_in:
            return SGP_OK
        ret = logout(self.handle)
        self.last_vendor_code = ret
        self._logged_in = False
        if ret != SGP_OK:
            logger.warning("Logout returned code: %d", ret)
        return SGP_OK if ret == SGP_OK else ret

    def release(self):
        """释放底层句柄。"""
        if self.handle is not None:
            try:
                uninit_device(self.handle)
            except Exception:
                pass
            self.handle = None

    def get_general_info(self):
        """获取通用信息。

        Returns
        -------
        tuple[int, SGP_GENERAL_INFO | None]
            (错误码, 信息结构或 None)。
        """
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED, None
        ret, info = get_general_info(self.handle)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("Get general info failed: %d", ret)
            self.last_error = SGP_ERR_GET_GENERAL_FAILED
            return SGP_ERR_GET_GENERAL_FAILED, None
        return SGP_OK, info

    def get_version_info(self):
        """获取版本信息。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED, None
        ret, info = get_version_info(self.handle)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("Get version info failed: %d", ret)
            self.last_error = SGP_ERR_GET_VERSION_FAILED
            return SGP_ERR_GET_VERSION_FAILED, None
        return SGP_OK, info

    def open_ir_video(self, callback: Callable, user_ptr: Optional[ct.c_void_p] = None):
        """开启红外视频流。

        Parameters
        ----------
        callback : Callable
            回调 (data_ptr, width, height, user_ptr)。
        user_ptr : c_void_p | None
            透传指针，可为 None。
        """
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        if self._video_opened:
            return SGP_OK
        if not isinstance(callback, SGP_RTSPCALLBACK):
            cb = SGP_RTSPCALLBACK(callback)
        else:
            cb = callback
        ret = open_ir_video(self.handle, cb, user_ptr)
        self.last_vendor_code = ret
        if ret == SGP_OK:
            self._video_opened = True
            self._video_callback = cb
            return SGP_OK
        logger.error("Open IR video failed: %d", ret)
        self.last_error = SGP_ERR_OPEN_VIDEO_FAILED
        return SGP_ERR_OPEN_VIDEO_FAILED

    def close_ir_video(self):
        """关闭红外视频流。"""
        if self.handle is None or not self._video_opened:
            return SGP_OK
        close_ir_video(self.handle)
        self._video_opened = False
        self._video_callback = None
        return SGP_OK

    def start_record(self, video_type: int, path: str, callback: Optional[Callable] = None, user_ptr: Optional[ct.c_void_p] = None):
        """开始录像。

        Parameters
        ----------
        video_type : int
            录像类型 (IR / VL)。
        path : str
            保存文件路径。
        callback : Callable | None
            录像反馈回调 (code, user_ptr)。
        user_ptr : c_void_p | None
            透传指针。
        """
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        if callback is None:
            def _empty_cb(code, user):
                pass
            callback = _empty_cb
        if not isinstance(callback, SGP_RECORDCALLBACK):
            cb = SGP_RECORDCALLBACK(callback)
        else:
            cb = callback
        ret = start_record(self.handle, video_type, path, cb, user_ptr)
        self.last_vendor_code = ret
        if ret == SGP_OK:
            self._record_callback = cb
            self._recording_types.add(int(video_type))
            return SGP_OK
        logger.error("Start record failed: %d", ret)
        self.last_error = SGP_ERR_RECORD_START_FAILED
        return SGP_ERR_RECORD_START_FAILED

    def stop_record(self, video_type: int):
        """停止指定类型录像。"""
        if self.handle is None or int(video_type) not in self._recording_types:
            return SGP_OK
        stop_record(self.handle, video_type)
        self._recording_types.discard(int(video_type))
        if not self._recording_types:
            self._record_callback = None
        return SGP_OK

    def screen_capture(self, image_type: int, path: str):
        """抓拍图像。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = screen_capture(self.handle, image_type, path)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("Screen capture failed: %d", ret)
            self.last_error = SGP_ERR_CAPTURE_FAILED
            return SGP_ERR_CAPTURE_FAILED
        return SGP_OK

    def get_heatmap(self, path: str):
        """获取热力图文件。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = get_heatmap(self.handle, path)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("Get heatmap failed: %d", ret)
            self.last_error = SGP_ERR_HEATMAP_FAILED
            return SGP_ERR_HEATMAP_FAILED
        return SGP_OK

    def get_image_temps(self, length: int, mat_type: int = 0):
        """获取温度矩阵并转换为 Python list。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED, None
        ret, buf = get_image_temps(self.handle, length, mat_type)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("GetImageTemps failed: %d", ret)
            self.last_error = SGP_ERR_GET_TEMPS_FAILED
            return SGP_ERR_GET_TEMPS_FAILED, None
        return SGP_OK, [buf[i] for i in range(length)]

    def get_thermometry_param(self):
        """获取测温参数。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED, None
        ret, p = get_thermometry_param(self.handle)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("Get thermometry param failed: %d", ret)
            self.last_error = SGP_ERR_GET_THERM_PARAM_FAILED
            return SGP_ERR_GET_THERM_PARAM_FAILED, None
        return SGP_OK, p

    def set_thermometry_param(self, param: SGP_THERMOMETRY_PARAM):
        """设置测温参数。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = set_thermometry_param(self.handle, param)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("SetThermometryParam failed: %d", ret)
            self.last_error = SGP_ERR_SET_THERM_PARAM_FAILED
            return SGP_ERR_SET_THERM_PARAM_FAILED
        return SGP_OK

    def do_shutter(self, shutter_type: int = SGP_SHUTTER):
        """执行快门。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = do_shutter(self.handle, shutter_type)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("DoShutter failed: %d", ret)
            self.last_error = SGP_ERR_SHUTTER_FAILED
            return SGP_ERR_SHUTTER_FAILED
        return SGP_OK

    def set_focus(self, focus_type: int, value: int = 0):
        """对焦。

        Parameters
        ----------
        focus_type : int
            聚焦类型 (自动/步进等)。
        value : int, default=0
            需要时传递的步进值。
        """
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = set_focus(self.handle, focus_type, value)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("SetFocus failed: %d", ret)
            self.last_error = SGP_ERR_FOCUS_FAILED
            return SGP_ERR_FOCUS_FAILED
        return SGP_OK

    def reboot(self):
        """远程重启。"""
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = reboot_system(self.handle)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("RebootSystem failed: %d", ret)
            self.last_error = SGP_ERR_REBOOT_FAILED
            return SGP_ERR_REBOOT_FAILED
        return SGP_OK

def error_text(code: int) -> str:
    """错误码转可读文本。未知码返回 'Unknown error (code)'。"""
    mapping = {
        SGP_OK: 'OK',
        SGP_ERR_NOT_INITIALIZED: 'Device not initialized',
        SGP_ERR_INIT_FAILED: 'Device init failed',
        SGP_ERR_LOGIN_FAILED: 'Login failed',
        SGP_ERR_OPEN_VIDEO_FAILED: 'Open IR video failed',
        SGP_ERR_RECORD_START_FAILED: 'Start record failed',
        SGP_ERR_CAPTURE_FAILED: 'Screen capture failed',
        SGP_ERR_HEATMAP_FAILED: 'Get heatmap failed',
        SGP_ERR_GET_TEMPS_FAILED: 'Get image temps failed',
        SGP_ERR_GET_GENERAL_FAILED: 'Get general info failed',
        SGP_ERR_GET_VERSION_FAILED: 'Get version info failed',
        SGP_ERR_GET_THERM_PARAM_FAILED: 'Get thermometry param failed',
        SGP_ERR_SET_THERM_PARAM_FAILED: 'Set thermometry param failed',
        SGP_ERR_SHUTTER_FAILED: 'Do shutter failed',
        SGP_ERR_FOCUS_FAILED: 'Set focus failed',
        SGP_ERR_REBOOT_FAILED: 'Reboot failed',
    }
    return mapping.get(code, f'Unknown error ({code})')

__all__ = [
    'init_device','uninit_device','login','logout','get_general_info','get_version_info',
    'open_ir_video','close_ir_video','start_record','stop_record','screen_capture','do_shutter',
    'get_heatmap','get_image_temps','get_thermometry_param','set_thermometry_param','reboot_system','set_focus',
    'cstr_to_py',
    'SGP_RANGE','SGP_GENERAL_INFO','SGP_VERSION_INFO','SGP_THERMOMETRY_PARAM','SGP_RTSPCALLBACK','SGP_RECORDCALLBACK',
    'SGP_VL_IMAGE','SGP_IR_IMAGE','SGP_VL_VIDEO','SGP_IR_VIDEO','SGP_SHUTTER','SGP_FOCUS_AUTO','SGP_OK',
    'IRCamera','SGP_ERR_NOT_INITIALIZED','SGP_ERR_INIT_FAILED','SGP_ERR_LOGIN_FAILED','SGP_ERR_OPEN_VIDEO_FAILED',
    'SGP_ERR_RECORD_START_FAILED','SGP_ERR_CAPTURE_FAILED','SGP_ERR_HEATMAP_FAILED','SGP_ERR_GET_TEMPS_FAILED',
    'SGP_ERR_GET_GENERAL_FAILED','SGP_ERR_GET_VERSION_FAILED','SGP_ERR_GET_THERM_PARAM_FAILED','SGP_ERR_SET_THERM_PARAM_FAILED',
    'SGP_ERR_SHUTTER_FAILED','SGP_ERR_FOCUS_FAILED','SGP_ERR_REBOOT_FAILED','error_text'
]
