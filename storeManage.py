"""storeManage
================

采集结果（图像、温度矩阵）存储参数管理。

功能概述
--------
- 路径创建与可写性校验
- 三类数据保存开关 (RGB 图像 / IR 伪彩图 / IR 温度矩阵)
- 与 QSettings (INI) 的读写同步

设计说明
--------
- 所有 set_* 方法返回 0 表示成功，非 0 表示失败，便于位或聚合。
- 提供 `coerce_bool` 统一宽松布尔解析，兼容 GUI/配置文件输入。
"""

import os
import logging

logger = logging.getLogger(__name__)

STORE_OK = 0


def coerce_bool(value):
    """宽松解析布尔值。

    支持类型
    --------
    - bool: 直接返回
    - int: 仅 0/1 合法
    - str: 支持 '1,true,yes,on,y' 为 True；'0,false,no,off,n' 为 False

    Parameters
    ----------
    value : Any
        待解析对象。

    Returns
    -------
    bool | None
        解析成功返回布尔值；无法识别返回 None。
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on", "y"}:
            return True
        if v in {"0", "false", "no", "off", "n"}:
            return False
    return None


class StoreManage:
    """采集存储参数管理器。

    Attributes
    ----------
    store_path : str
        存储目录（默认: <当前工作目录>/records）。
    save_rgb_img : bool
        是否保存 RGB 图像。
    save_ir_img : bool
        是否保存 IR 伪彩图。
    save_ir_temp : bool
        是否保存 IR 温度矩阵(JSON)。

    """

    def __init__(self):
        self.store_path = os.path.join(os.getcwd(), 'records')
        if not os.path.exists(self.store_path):
            try:
                os.makedirs(self.store_path, exist_ok=True)
            except Exception as e:
                logger.error("Create store path failed on init: %s", e)
        self.save_rgb_img = True
        self.save_ir_img = True
        self.save_ir_temp = True

    def _reset_param(self):
        """重置为默认参数."""
        self.store_path = os.path.join(os.getcwd(), 'records')
        self.save_rgb_img = True
        self.save_ir_img = True
        self.save_ir_temp = True

    def set_store_path(self, path: str):
        """设置存储目录。

        规则
        ----
        - 非空字符串
        - 若目录不存在则尝试创建
        - 创建失败返回非 0

        Parameters
        ----------
        path : str
            目标目录路径。

        Returns
        -------
        int
            0 成功；非 0 失败。
        """
        if not isinstance(path, str) or not path.strip():
            logger.error("Set store path failed: illegal parameter")
            return not STORE_OK
        path = os.path.abspath(path)
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            logger.error("Set store path failed: can not create %s (%s)", path, e)
            return not STORE_OK
        self.store_path = path
        logger.info("Set store path successes: %s", path)
        return STORE_OK

    def set_save_rgb_img(self, flag):
        """设置是否保存可见光图像."""
        b = coerce_bool(flag)
        if b is None:
            logger.error("Set save_rgb_img failed: illegal parameter")
            return not STORE_OK
        self.save_rgb_img = b
        logger.info("Set save_rgb_img successes: %s", b)
        return STORE_OK

    def set_save_ir_img(self, flag):
        """设置是否保存红外图像."""
        b = coerce_bool(flag)
        if b is None:
            logger.error("Set save_ir_img failed: illegal parameter")
            return not STORE_OK
        self.save_ir_img = b
        logger.info("Set save_ir_img successes: %s", b)
        return STORE_OK

    def set_save_ir_temp(self, flag):
        """设置是否保存温度矩阵."""
        b = coerce_bool(flag)
        if b is None:
            logger.error("Set save_ir_temp failed: illegal parameter")
            return not STORE_OK
        self.save_ir_temp = b
        logger.info("Set save_ir_temp successes: %s", b)
        return STORE_OK

    def load_param_from_file(self, config):
        """从 QSettings 读取参数。

        Key
        ---
        STORE/PATH, STORE/SAVE_RGB_IMG, STORE/SAVE_IR_IMG, STORE/SAVE_IR_TEMP

        Parameters
        ----------
        config : QSettings
            配置实例。

        Returns
        -------
        int
            0 成功；非法则重置并返回非 0。
        """
        path = config.value("STORE/PATH", 0)
        rgb = config.value("STORE/SAVE_RGB_IMG", "-1")
        ir = config.value("STORE/SAVE_IR_IMG", "-1")
        temp = config.value("STORE/SAVE_IR_TEMP", "-1")
        ret = self.set_store_path(path)
        ret |= self.set_save_rgb_img(rgb)
        ret |= self.set_save_ir_img(ir)
        ret |= self.set_save_ir_temp(temp)
        if ret == STORE_OK:
            logger.info(
                "Load store param successes: path=%s, rgb=%s, ir=%s, temp=%s",
                self.store_path, self.save_rgb_img, self.save_ir_img, self.save_ir_temp
            )
            return STORE_OK
        logger.error("Load store param failed: reset to default")
        self.reset_param_of_file(config)
        return not STORE_OK

    def save_param_to_file(self, config):
        """保存当前参数到 QSettings。

        Parameters
        ----------
        config : QSettings
            配置实例。

        Returns
        -------
        int
            0 成功；非 0 失败。
        """
        if not hasattr(config, 'setValue'):
            logger.error("Save param failed: config has no setValue() method")
            return not STORE_OK
        config.setValue("STORE/PATH", self.store_path)
        config.setValue("STORE/SAVE_RGB_IMG", int(self.save_rgb_img))
        config.setValue("STORE/SAVE_IR_IMG", int(self.save_ir_img))
        config.setValue("STORE/SAVE_IR_TEMP", int(self.save_ir_temp))
        logger.info(
            "Save store param successes: path=%s, rgb=%s, ir=%s, temp=%s",
            self.store_path, self.save_rgb_img, self.save_ir_img, self.save_ir_temp
        )
        return STORE_OK

    def reset_param_of_file(self, config):
        """重置为默认并写入 QSettings。

        Parameters
        ----------
        config : QSettings
            配置实例。

        Returns
        -------
        int
            0 表示成功。
        """
        self._reset_param()
        logger.info("Reset store param successes")
        self.save_param_to_file(config)
        logger.info("Reset store param of file successes")
        return STORE_OK
