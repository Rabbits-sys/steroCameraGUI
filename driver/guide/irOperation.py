import os
import ctypes as ct
from typing import Optional, Callable, List
import logging

# Setup logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')

# Constants matching SgpParam.h
STRING_LENGH = 50
RANGE_MAX_NUM = 3
SGP_OK = 0
SGP_ERR_NOT_INITIALIZED = -1001  # 自定义: 设备未初始化
SGP_ERR_INIT_FAILED = -1002      # 初始化失败
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

# Enums/defines we use
SGP_VL_IMAGE = 1
SGP_IR_IMAGE = 2

SGP_VL_VIDEO = 1
SGP_IR_VIDEO = 2

SGP_SHUTTER = 1
SGP_FOCUS_AUTO = 5

# Types
SGP_HANDLE = ct.c_ulonglong

# Resolve DLL directory (parent folder contains SgpApi.dll)
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure dependent DLLs can be found on Windows 10+ / Python 3.8+
if hasattr(os, 'add_dll_directory'):
    try:
        os.add_dll_directory(_ROOT_DIR)
    except FileNotFoundError:
        pass

_DLL_PATH = os.path.join(_ROOT_DIR, 'SgpApi.dll')
if not os.path.isfile(_DLL_PATH):
    raise FileNotFoundError('SgpApi.dll not found at: %s' % _DLL_PATH)

# Use cdecl (CDLL) per header (no stdcall macro present)
_lib = ct.CDLL(_DLL_PATH)

# Structures matching SgpParam.h
class SGP_RANGE(ct.Structure):
    _fields_ = [
        ('min', ct.c_int),
        ('max', ct.c_int),
    ]

class SGP_GENERAL_INFO(ct.Structure):
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
    _fields_ = [
        ('model', ct.c_char * STRING_LENGH),
        ('version', ct.c_char * STRING_LENGH),
        ('serial', ct.c_char * STRING_LENGH),
        ('fpga_version', ct.c_char * STRING_LENGH),
        ('measure_version', ct.c_char * STRING_LENGH),
        ('sdk_version', ct.c_char * STRING_LENGH),
    ]

class SGP_THERMOMETRY_PARAM(ct.Structure):
    _fields_ = [
        ('color_bar', ct.c_int),
        ('color_show', ct.c_int),
        ('flag', ct.c_int),
        ('mod_temp', ct.c_float),
        ('show_mode', ct.c_int),
        ('gear', ct.c_int),
        ('show_string', ct.c_int),
        ('show_desc', ct.c_char * STRING_LENGH),
        ('atmo_trans', ct.c_float),
        ('dist', ct.c_float),
        ('emiss', ct.c_float),
        ('emiss_mode', ct.c_int),
        ('humi', ct.c_int),
        ('opti_trans', ct.c_float),
        ('ref_temp', ct.c_float),
        ('isot_flag', ct.c_int),
        ('isot_high', ct.c_float),
        ('isot_high_color', ct.c_char * STRING_LENGH),
        ('isot_low', ct.c_int),
        ('isot_low_color', ct.c_char * STRING_LENGH),
        ('isot_type', ct.c_int),
        ('ambient', ct.c_float),
    ]

# Callback types (cdecl)
SGP_RTSPCALLBACK = ct.CFUNCTYPE(None, ct.POINTER(ct.c_ubyte), ct.c_int, ct.c_int, ct.c_void_p)
SGP_RECORDCALLBACK = ct.CFUNCTYPE(None, ct.c_int, ct.c_void_p)

# Function prototypes
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

# Pythonic wrapper helpers

def init_device() -> int:
    return int(_lib.SGP_InitDevice())


def uninit_device(handle: int) -> None:
    _lib.SGP_UnInitDevice(SGP_HANDLE(handle))


def login(handle: int, server: str, username: str, password: str, port: int) -> int:
    return int(_lib.SGP_Login(SGP_HANDLE(handle), server.encode('utf-8'), username.encode('utf-8'), password.encode('utf-8'), int(port)))


def logout(handle: int) -> int:
    return int(_lib.SGP_Logout(SGP_HANDLE(handle)))


def get_general_info(handle: int):
    # Low-level wrapper: always return (ret, info)
    info = SGP_GENERAL_INFO()
    ret = _lib.SGP_GetGeneralInfo(SGP_HANDLE(handle), ct.byref(info))
    return ret, info


def get_version_info(handle: int):
    info = SGP_VERSION_INFO()
    ret = _lib.SGP_GetVersionInfo(SGP_HANDLE(handle), ct.byref(info))
    return ret, info


def open_ir_video(handle: int, callback: SGP_RTSPCALLBACK, user_ptr: ct.c_void_p = None) -> int:
    return int(_lib.SGP_OpenIrVideo(SGP_HANDLE(handle), callback, user_ptr))


def close_ir_video(handle: int) -> None:
    _lib.SGP_CloseIrVideo(SGP_HANDLE(handle))


def start_record(handle: int, video_type: int, path: str, callback: SGP_RECORDCALLBACK, user_ptr: ct.c_void_p = None) -> int:
    return int(_lib.SGP_StartRecord(SGP_HANDLE(handle), int(video_type), path.encode('utf-8'), callback, user_ptr))


def stop_record(handle: int, video_type: int) -> None:
    _lib.SGP_StopRecord(SGP_HANDLE(handle), int(video_type))


def screen_capture(handle: int, image_type: int, path: str) -> int:
    return int(_lib.SGP_GetScreenCapture(SGP_HANDLE(handle), int(image_type), path.encode('utf-8')))


def do_shutter(handle: int, shutter_type: int) -> int:
    return int(_lib.SGP_DoShutter(SGP_HANDLE(handle), int(shutter_type)))


def get_heatmap(handle: int, path: str) -> int:
    return int(_lib.SGP_GetHeatMap(SGP_HANDLE(handle), path.encode('utf-8')))


def get_image_temps(handle: int, length: int, mat_type: int = 0):
    buf = (ct.c_float * length)()
    ret = _lib.SGP_GetImageTemps(SGP_HANDLE(handle), buf, int(length * 4), int(mat_type))
    return ret, buf


def get_thermometry_param(handle: int):
    param = SGP_THERMOMETRY_PARAM()
    ret = _lib.SGP_GetThermometryParam(SGP_HANDLE(handle), ct.byref(param))
    return ret, param


def set_thermometry_param(handle: int, p: SGP_THERMOMETRY_PARAM) -> int:
    return int(_lib.SGP_SetThermometryParam(SGP_HANDLE(handle), p))


def reboot_system(handle: int) -> int:
    return int(_lib.SGP_RebootSystem(SGP_HANDLE(handle)))


def set_focus(handle: int, focus_type: int, value: int = 0) -> int:
    return int(_lib.SGP_SetFocus(SGP_HANDLE(handle), int(focus_type), int(value)))

# Utility to decode char arrays

def cstr_to_py(b: bytes) -> str:
    if not b:
        return ''
    try:
        # Try GBK first (Qt fromLocal8Bit often maps to ANSI/GBK on CN Windows)
        return b.split(b'\x00', 1)[0].decode('gbk', errors='ignore')
    except Exception:
        return b.split(b'\x00', 1)[0].decode('utf-8', errors='ignore')


# ---------------------------------------------------------------------------
# IRCamera 面向对象封装
# ---------------------------------------------------------------------------
class IRCamera:
    """IR 相机封装类

    所有方法返回自定义错误码：
      - 成功: SGP_OK
      - 失败: 负值 (见下方常量)
    有数据返回的函数: (ret, data|None)

    可通过: last_error 获取最近一次框架错误码, last_vendor_code 获取底层 SDK 原始返回值。
    使用 error_text(ret) 转换错误码为文字说明。
    """

    def __init__(self, server: str, username: str, password: str, port: int = 80):
        self.server = server
        self.username = username
        self.password = password
        self.port = int(port)
        self.handle: Optional[int] = None
        self._logged_in: bool = False
        self._video_opened: bool = False
        self._video_callback: Optional[Callable] = None  # keep reference
        self._record_callback: Optional[Callable] = None  # keep reference
        self._recording_types: set[int] = set()
        self.last_error: int = SGP_OK
        self.last_vendor_code: int = SGP_OK
        self._init_device()

    # -------- 内部工具 --------
    def _ensure_handle(self):
        if self.handle is None:
            self.last_error = SGP_ERR_NOT_INITIALIZED
            logger.error("IRCamera device handle is None (not initialized)")
            return SGP_ERR_NOT_INITIALIZED
        return SGP_OK

    def _init_device(self):
        if self.handle is None:
            self.handle = init_device()
            if not isinstance(self.handle, int) or self.handle == 0:
                self.last_error = SGP_ERR_INIT_FAILED
                self.last_vendor_code = 0
                logger.error("Init device failed, handle=0")

    # -------- 上下文管理 --------
    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.close_ir_video()
        except Exception:
            pass
        try:
            # 停止可能还在进行的录像
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
        try:
            if self._logged_in:
                self.logout()
            self.release()
        except Exception:
            pass

    # -------- 基础控制 --------
    def login(self):
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
        if self.handle is None or not self._logged_in:
            return SGP_OK
        ret = logout(self.handle)
        self.last_vendor_code = ret
        self._logged_in = False
        if ret != SGP_OK:
            logger.warning("Logout returned code: %d", ret)
        return SGP_OK if ret == SGP_OK else ret

    def release(self):
        if self.handle is not None:
            try:
                uninit_device(self.handle)
            except Exception:
                pass
            self.handle = None

    # -------- 信息查询 --------
    def get_general_info(self):
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
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED, None
        ret, info = get_version_info(self.handle)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("Get version info failed: %d", ret)
            self.last_error = SGP_ERR_GET_VERSION_FAILED
            return SGP_ERR_GET_VERSION_FAILED, None
        return SGP_OK, info

    # -------- 视频流 --------
    def open_ir_video(self, callback: Callable, user_ptr: Optional[ct.c_void_p] = None):
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
        if self.handle is None or not self._video_opened:
            return SGP_OK
        close_ir_video(self.handle)
        self._video_opened = False
        self._video_callback = None
        return SGP_OK

    # -------- 录像 --------
    def start_record(self, video_type: int, path: str, callback: Optional[Callable] = None, user_ptr: Optional[ct.c_void_p] = None):
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        if callback is None:
            # 默认空回调
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
        if self.handle is None or int(video_type) not in self._recording_types:
            return SGP_OK
        stop_record(self.handle, video_type)
        self._recording_types.discard(int(video_type))
        if not self._recording_types:
            self._record_callback = None
        return SGP_OK

    # -------- 抓图 / 热力图 --------
    def screen_capture(self, image_type: int, path: str):
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
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = get_heatmap(self.handle, path)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("Get heatmap failed: %d", ret)
            self.last_error = SGP_ERR_HEATMAP_FAILED
            return SGP_ERR_HEATMAP_FAILED
        return SGP_OK

    # -------- 温度矩阵 --------
    def get_image_temps(self, length: int, mat_type: int = 0):
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED, None
        ret, buf = get_image_temps(self.handle, length, mat_type)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("GetImageTemps failed: %d", ret)
            self.last_error = SGP_ERR_GET_TEMPS_FAILED
            return SGP_ERR_GET_TEMPS_FAILED, None
        return SGP_OK, [buf[i] for i in range(length)]

    # -------- 测温参数 --------
    def get_thermometry_param(self):
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
        if self._ensure_handle() != SGP_OK:
            return SGP_ERR_NOT_INITIALIZED
        ret = set_thermometry_param(self.handle, param)
        self.last_vendor_code = ret
        if ret != SGP_OK:
            logger.error("SetThermometryParam failed: %d", ret)
            self.last_error = SGP_ERR_SET_THERM_PARAM_FAILED
            return SGP_ERR_SET_THERM_PARAM_FAILED
        return SGP_OK

    # -------- 其它控制 --------
    def do_shutter(self, shutter_type: int = SGP_SHUTTER):
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
    # 原函数
    'init_device','uninit_device','login','logout','get_general_info','get_version_info',
    'open_ir_video','close_ir_video','start_record','stop_record','screen_capture','do_shutter',
    'get_heatmap','get_image_temps','get_thermometry_param','set_thermometry_param','reboot_system','set_focus',
    'cstr_to_py',
    # 类型 & 常量
    'SGP_RANGE','SGP_GENERAL_INFO','SGP_VERSION_INFO','SGP_THERMOMETRY_PARAM','SGP_RTSPCALLBACK','SGP_RECORDCALLBACK',
    'SGP_VL_IMAGE','SGP_IR_IMAGE','SGP_VL_VIDEO','SGP_IR_VIDEO','SGP_SHUTTER','SGP_FOCUS_AUTO','SGP_OK',
    # 新增类 & 自定义错误码
    'IRCamera','SGP_ERR_NOT_INITIALIZED','SGP_ERR_INIT_FAILED','SGP_ERR_LOGIN_FAILED','SGP_ERR_OPEN_VIDEO_FAILED',
    'SGP_ERR_RECORD_START_FAILED','SGP_ERR_CAPTURE_FAILED','SGP_ERR_HEATMAP_FAILED','SGP_ERR_GET_TEMPS_FAILED',
    'SGP_ERR_GET_GENERAL_FAILED','SGP_ERR_GET_VERSION_FAILED','SGP_ERR_GET_THERM_PARAM_FAILED','SGP_ERR_SET_THERM_PARAM_FAILED',
    'SGP_ERR_SHUTTER_FAILED','SGP_ERR_FOCUS_FAILED','SGP_ERR_REBOOT_FAILED','error_text'
]
