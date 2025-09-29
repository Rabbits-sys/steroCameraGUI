import ctypes as ct
import logging
from typing import Optional, Callable

from driver.guide.irOperation import (SGP_OK, init_device, login, logout, uninit_device, get_general_info
    , get_version_info, open_ir_video, close_ir_video, start_record, stop_record, screen_capture
    , get_heatmap, get_image_temps, get_thermometry_param, set_thermometry_param, do_shutter
    , set_focus, reboot_system)
from driver.guide.irOperation import SGP_RTSPCALLBACK, SGP_RECORDCALLBACK, SGP_THERMOMETRY_PARAM, SGP_SHUTTER

logger = logging.getLogger(__name__)

class IRCamera(object):
    """红外相机高级封装。

    负责统一管理以下能力：设备初始化/登录注销、红外视频获取、录像控制、抓图、热力图导出、温度矩阵获取、测温参数读写、执行快门、聚焦与远程重启等。

    Notes
    -----
    - 所有方法若返回 ``SGP_OK`` 表示成功；返回 ``not SGP_OK`` (通常为 1) 表示失败。
    - 为兼容底层 SDK，错误时统一返回简单整数而非抛出异常；调用侧可按需封装。
    - ``not SGP_OK`` 的写法依赖于 ``SGP_OK == 0`` 的事实，保持与原实现一致。

    Attributes
    ----------
    param : IRCameraParam
        当前连接参数配置对象。
    handle : int | None
        底层 SDK 设备句柄；``None`` 或 ``0`` 代表未初始化/失效。
    _logged_in : bool
        是否已登录。
    _video_opened : bool
        红外视频是否已开启。
    _video_callback : Callable | None
        当前视频帧回调（SDK 回调包装）。
    _record_callback : Callable | None
        当前录像状态回调。
    _recording_types : set[int]
        正在录像的类型集合（可能同时存在多种录像类型）。
    """
    def __init__(self):
        self.param = IRCameraParam()
        self.handle: Optional[int] = None
        self._logged_in: bool = False
        self._video_opened: bool = False
        self._video_callback: Optional[Callable] = None
        self._record_callback: Optional[Callable] = None
        self._recording_types: set[int] = set()
        self._init_device()

    def _ensure_handle(self):
        """校验底层句柄有效性。

        Returns
        -------
        int
            ``SGP_OK`` 表示有效；否则返回错误码 (``not SGP_OK``)。
        """
        if self.handle is None:
            logger.error("IRCamera device handle is None (not initialized)")
            return not SGP_OK
        return SGP_OK

    def _init_device(self):
        """初始化底层设备（仅首次生效）。

        若句柄已经存在则忽略。初始化失败时记录错误日志，不抛异常。
        """
        if self.handle is None:
            self.handle = init_device()
            if not isinstance(self.handle, int) or self.handle == 0:
                logger.error("Init device failed, handle = 0")
            logger.info("Init device successes, handle = %s", self.handle)

    def __del__(self):
        """析构时的兜底清理。

        若仍处于登录或占用状态，尝试释放相关资源。忽略所有异常。
        """
        try:
            if self._video_opened:
                self.close_ir_video()
            if self._logged_in:
                self.logout()
            self.release()
        except Exception:
            pass

    def login(self):
        """登录设备。

        已登录则直接返回成功。

        Returns
        -------
        int
            ``SGP_OK`` 成功，否则失败。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        if self._logged_in:
            logger.warning("Already logged in")
            return SGP_OK
        ret = login(self.handle, self.param.server, self.param.username, self.param.password, self.param.port)
        if ret == SGP_OK:
            self._logged_in = True
            logger.info("Login successes")
            return SGP_OK
        logger.error("Login failed: %d", ret)
        return not SGP_OK

    def logout(self):
        """注销登录。

        未登录时视为成功。

        Returns
        -------
        int
            ``SGP_OK`` 成功；否则失败。
        """
        if self.handle is None or not self._logged_in:
            logger.warning("Already logout")
            # return SGP_OK
        ret = logout(self.handle)
        self._logged_in = False
        if ret == SGP_OK:
            logger.info("Logout successes")
            return SGP_OK
        logger.warning("Logout failed: %d", ret)
        return not SGP_OK

    def release(self):
        """释放底层句柄资源。

        若句柄为 ``None`` 则忽略。失败仅记录警告。
        """
        if self.handle is not None:
            try:
                uninit_device(self.handle)
                logger.info("Release handle successes")
            except Exception:
                logger.warning("Release handle failed")
            self.handle = None

    def get_general_info(self):
        """获取设备通用信息。

        Returns
        -------
        tuple[int, SGP_GENERAL_INFO | None]
            (错误码, 信息结构)。失败时信息为 ``None``。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK, None
        ret, info = get_general_info(self.handle)
        if ret == SGP_OK:
            logger.info("Get general info successes")
            return SGP_OK, info
        logger.error("Get general info failed: %d", ret)
        return not SGP_OK, None

    def get_version_info(self):
        """获取 SDK / 设备版本信息。

        Returns
        -------
        tuple[int, SGP_VERSION_INFO | None]
            (错误码, 版本信息)；失败时版本信息为 ``None``。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK, None
        ret, info = get_version_info(self.handle)
        if ret == SGP_OK:
            logger.info("Get version info successes")
            return SGP_OK, info
        logger.error("Get version info failed: %d", ret)
        return not SGP_OK, None

    def open_ir_video(self, callback: Callable, user_ptr: Optional[ct.c_void_p] = None):
        """开启红外视频流。

        Parameters
        ----------
        callback : Callable
            视频帧回调，签名 ``(data_ptr, width, height, user_ptr)``。
        user_ptr : c_void_p, optional
            透传指针，可为 ``None``。

        Returns
        -------
        int
            ``SGP_OK`` 成功；已开启或失败返回对应状态。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        if self._video_opened:
            logger.warning("Already open IR video")
            return SGP_OK
        if not isinstance(callback, SGP_RTSPCALLBACK):
            cb = SGP_RTSPCALLBACK(callback)
        else:
            cb = callback
        ret = open_ir_video(self.handle, cb, user_ptr)
        if ret == SGP_OK:
            self._video_opened = True
            self._video_callback = cb
            logger.info("Open IR video successes")
            return SGP_OK
        logger.error("Open IR video failed: %d", ret)
        return not SGP_OK

    def close_ir_video(self):
        """关闭红外视频流。

        Returns
        -------
        int
            ``SGP_OK``（即便已关闭也返回成功）。
        """
        if self.handle is None or not self._video_opened:
            logger.warning("Already close IR video")
            return SGP_OK
        close_ir_video(self.handle)
        self._video_opened = False
        self._video_callback = None
        logger.info("Close IR video successes")
        return SGP_OK

    def start_record(self, video_type: int, path: str, callback: Optional[Callable] = None, user_ptr: Optional[ct.c_void_p] = None):
        """开始录像。

        Parameters
        ----------
        video_type : int
            录像类型（IR / VL 等，根据底层定义）。
        path : str
            保存文件完整路径。
        callback : Callable, optional
            录像反馈回调，签名 ``(code, user_ptr)``；为 ``None`` 时采用空回调。
        user_ptr : c_void_p, optional
            透传指针。

        Returns
        -------
        int
            ``SGP_OK`` 成功，否则失败。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        if callback is None:
            def _empty_cb(code, user):
                pass
            callback = _empty_cb
        if not isinstance(callback, SGP_RECORDCALLBACK):
            cb = SGP_RECORDCALLBACK(callback)
        else:
            cb = callback
        ret = start_record(self.handle, video_type, path, cb, user_ptr)
        if ret == SGP_OK:
            self._record_callback = cb
            self._recording_types.add(int(video_type))
            logger.info("Start record successes")
            return SGP_OK
        logger.error("Start record failed: %d", ret)
        return not SGP_OK

    def stop_record(self, video_type: int):
        """停止指定类型录像。

        Parameters
        ----------
        video_type : int
            要停止的录像类型。

        Returns
        -------
        int
            ``SGP_OK``（即便该类型未在录像也返回成功）。
        """
        if self.handle is None or int(video_type) not in self._recording_types:
            logger.warning("Already close record type %d", video_type)
            return SGP_OK
        stop_record(self.handle, video_type)
        self._recording_types.discard(int(video_type))
        if not self._recording_types:
            self._record_callback = None
        logger.info("Close record type %d", video_type)
        return SGP_OK

    def screen_capture(self, image_type: int, path: str):
        """抓拍一帧图像并保存。

        Parameters
        ----------
        image_type : int
            图像类型（IR / 可见光等，取决于底层定义）。
        path : str
            保存路径（含文件名）。

        Returns
        -------
        int
            ``SGP_OK`` 成功；否则失败。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        ret = screen_capture(self.handle, image_type, path)
        if ret == SGP_OK:
            logger.info("Screen capture successes")
            return SGP_OK
        logger.error("Screen capture failed: %d", ret)
        return not SGP_OK

    def get_heatmap(self, path: str):
        """导出热力图文件。

        Parameters
        ----------
        path : str
            输出文件路径。

        Returns
        -------
        int
            ``SGP_OK`` 成功；否则失败。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        ret = get_heatmap(self.handle, path)
        if ret == SGP_OK:
            logger.info("Get heatmap successes")
            return SGP_OK
        logger.error("Get heatmap failed: %d", ret)
        return not SGP_OK

    def get_image_temps(self, length: int, mat_type: int = 0):
        """获取温度矩阵并转换为 Python list。

        Parameters
        ----------
        length : int
            预期温度数据长度（像素数）。
        mat_type : int, default=0
            底层矩阵类型标识。

        Returns
        -------
        tuple[int, list[float] | None]
            (错误码, 温度列表)；失败时列表为 ``None``。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK, None
        ret, buf = get_image_temps(self.handle, length, mat_type)
        if ret == SGP_OK:
            logger.info("Get image temps successes")
            return SGP_OK, [buf[i] for i in range(length)]
        logger.error("Get image temps failed: %d", ret)
        return not SGP_OK, None

    def get_thermometry_param(self):
        """读取测温参数。

        Returns
        -------
        tuple[int, SGP_THERMOMETRY_PARAM | None]
            (错误码, 参数结构)；失败时结构为 ``None``。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK, None
        p = get_thermometry_param(self.handle)
        if p:
            logger.info("Get thermometry param successes")
            return SGP_OK, p
        logger.error("Get thermometry param failed: %d", ret)
        return not SGP_OK, None

    def set_thermometry_param(self, param: SGP_THERMOMETRY_PARAM):
        """写入测温参数。

        Parameters
        ----------
        param : SGP_THERMOMETRY_PARAM
            待写入的参数结构。

        Returns
        -------
        int
            成功返回 ``SGP_OK``，失败返回错误码。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        ret = set_thermometry_param(self.handle, param)
        if ret == SGP_OK:
            logger.info("Set thermometry param successes")
            return SGP_OK
        logger.error("Set thermometry param failed: %d", ret)
        return not SGP_OK

    def do_shutter(self, shutter_type: int = SGP_SHUTTER):
        """执行快门操作。

        Parameters
        ----------
        shutter_type : int, default=SGP_SHUTTER
            快门类型/模式。

        Returns
        -------
        int
            ``SGP_OK`` 成功；否则失败。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        ret = do_shutter(self.handle, shutter_type)
        if ret == SGP_OK:
            logger.info("Do shutter successes")
            return SGP_OK
        logger.error("DoShutter failed: %d", ret)
        return not SGP_OK

    def set_focus(self, focus_type: int, value: int = 0):
        """对焦操作。

        Parameters
        ----------
        focus_type : int
            聚焦类型（自动/步进等）。
        value : int, default=0
            当为步进聚焦时的步进值。

        Returns
        -------
        int
            ``SGP_OK`` 成功；否则失败。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        ret = set_focus(self.handle, focus_type, value)
        if ret == SGP_OK:
            logger.info("Set focus successes")
            return SGP_OK
        logger.error("Set focus failed: %d", ret)
        return not SGP_OK

    def reboot(self):
        """远程重启设备。

        Returns
        -------
        int
            ``SGP_OK`` 成功；否则失败。
        """
        if self._ensure_handle() != SGP_OK:
            return not SGP_OK
        ret = reboot_system(self.handle)
        if ret == SGP_OK:
            logger.info("Reboot system successes")
            return SGP_OK
        logger.error("Reboot system failed: %d", ret)
        return not SGP_OK

class IRCameraParam(object):
    """红外相机连接与认证参数容器。

    负责保存/校验/读写到配置文件 (QSettings) 的参数。

    Attributes
    ----------
    server : str
        设备地址或主机名。
    username : str
        登录用户名。
    password : str
        登录密码。
    port : int
        服务端口。
    """
    def __init__(self):
        self.server: str = '192.168.1.168'
        self.username: str = 'admin'
        self.password: str = 'admin123'
        self.port: int = 80

    def _reset_param(self):
        """重置为默认参数。"""
        self.server = '192.168.1.168'
        self.username = 'admin'
        self.password = 'admin123'
        self.port = 80

    def set_server(self, server: str):
        """设置服务器地址/主机名。

        规则：非空；只含字母、数字、点、横线、下划线；长度 ≤ 255。

        Parameters
        ----------
        server : str
            新服务器地址或主机名。

        Returns
        -------
        int
            ``SGP_OK`` 成功；非法返回错误码。
        """
        if not isinstance(server, str) or not server:
            logger.error("Set server failed: illegal parameter")
            return not SGP_OK
        if len(server) > 255 or not __import__('re').match(r'^[A-Za-z0-9_.-]+$', server):
            logger.error("Set server failed: %s is not a valid server address", server)
            return not SGP_OK
        self.server = server
        logger.info("Set server successes: %s", server)
        return SGP_OK

    def set_username(self, username: str):
        """设置用户名。

        规则：非空且长度 ≤ 128。

        Parameters
        ----------
        username : str
            新用户名。

        Returns
        -------
        int
            ``SGP_OK`` 成功；非法返回错误码。
        """
        if not isinstance(username, str) or not username or len(username) > 128:
            logger.error("Set username failed: illegal parameter")
            return not SGP_OK
        self.username = username
        logger.info("Set username successes: %s", username)
        return SGP_OK

    def set_password(self, password: str):
        """设置密码。

        规则：非空且长度 ≤ 256。

        Parameters
        ----------
        password : str
            新密码。

        Returns
        -------
        int
            ``SGP_OK`` 成功；非法返回错误码。
        """
        if not isinstance(password, str) or not password or len(password) > 256:
            logger.error("Set password failed: illegal parameter")
            return not SGP_OK
        self.password = password
        logger.info("Set password successes")
        return SGP_OK

    def set_port(self, port: str):
        """设置端口。

        合法范围 1~65535；支持字符串自动转换。

        Parameters
        ----------
        port : int | str
            端口值或其字符串。

        Returns
        -------
        int
            ``SGP_OK`` 成功；非法返回错误码。
        """
        try:
            p = int(port)
        except (TypeError, ValueError):
            logger.error("Set port failed: illegal parameter")
            return not SGP_OK
        if p < 1 or p > 65535:
            logger.error("Set port failed: %d is not a valid port", p)
            return not SGP_OK
        self.port = p
        logger.info("Set port successes: %d", p)
        return SGP_OK

    def load_param_from_file(self, config):
        """从 QSettings 读取参数。

        若读取或校验失败，将回退为默认值并写回文件。

        Parameters
        ----------
        config : QSettings
            配置对象。

        Returns
        -------
        int
            ``SGP_OK`` 成功；失败返回错误码。
        """
        server = config.value("GUIDE/SERVER", 0)
        username = config.value("GUIDE/USERNAME", 0)
        password = config.value("GUIDE/PASSWORD", 0)
        port = config.value("GUIDE/PORT", 80)
        ret = self.set_server(server)
        ret |= self.set_username(username)
        ret |= self.set_password(password)
        ret |= self.set_port(port)
        if ret == SGP_OK:
            logger.info("Load param successes: sever=%s, username=%s, port=%d", self.server, self.username, self.port)
            return SGP_OK
        logger.error("Load param failed: reset to default")
        self.reset_param_of_file(config)
        return not SGP_OK

    def save_param_to_file(self, config):
        """将当前参数保存到 QSettings。

        Parameters
        ----------
        config : QSettings
            配置对象。
        """
        config.setValue("GUIDE/SERVER", self.server)
        config.setValue("GUIDE/USERNAME", self.username)
        config.setValue("GUIDE/PASSWORD", self.password)
        config.setValue("GUIDE/PORT", self.port)
        logger.info("Save param successes: sever=%s, username=%s, port=%d", self.server, self.username, self.port)

    def reset_param_of_file(self, config):
        """重置为默认参数并写入 QSettings。

        Parameters
        ----------
        config : QSettings
            配置对象。
        """
        self._reset_param()
        logger.info("Reset param successes")
        self.save_param_to_file(config)
        logger.info("Reset param of file successes")

