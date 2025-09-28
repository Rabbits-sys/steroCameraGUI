import os
import ctypes as ct

# Constants matching SgpParam.h
STRING_LENGH = 50
RANGE_MAX_NUM = 3
SGP_OK = 0

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
_ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sdk')

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


def get_general_info(handle: int) -> SGP_GENERAL_INFO:
    info = SGP_GENERAL_INFO()
    ret = _lib.SGP_GetGeneralInfo(SGP_HANDLE(handle), ct.byref(info))
    if ret != SGP_OK:
        raise RuntimeError('SGP_GetGeneralInfo failed: %d' % ret)
    return info


def get_version_info(handle: int) -> SGP_VERSION_INFO:
    info = SGP_VERSION_INFO()
    ret = _lib.SGP_GetVersionInfo(SGP_HANDLE(handle), ct.byref(info))
    if ret != SGP_OK:
        raise RuntimeError('SGP_GetVersionInfo failed: %d' % ret)
    return info


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


def get_thermometry_param(handle: int) -> SGP_THERMOMETRY_PARAM:
    p = SGP_THERMOMETRY_PARAM()
    ret = _lib.SGP_GetThermometryParam(SGP_HANDLE(handle), ct.byref(p))
    if ret != SGP_OK:
        raise RuntimeError('SGP_GetThermometryParam failed: %d' % ret)
    return p


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
