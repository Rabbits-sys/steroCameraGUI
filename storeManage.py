import os
import logging

logger = logging.getLogger(__name__)

STORE_OK = 0


def coerce_bool(value):
    """尽可能宽松地把输入转换为布尔值。

    支持: bool/int/str。字符串接受: '1','true','yes','on','y' 等为真；'0','false','no','off','n' 为假。
    不能识别则返回 None。
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
        """重置为默认参数。"""
        self.store_path = os.path.join(os.getcwd(), 'records')
        self.save_rgb_img = True
        self.save_ir_img = True
        self.save_ir_temp = True

    # ----------------------------- Setters -----------------------------
    def set_store_path(self, path: str):
        """设置存储目录。

        规则: 非空字符串；若不存在则尝试创建；失败返回错误。
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
        """设置是否保存可见光图像。"""
        b = coerce_bool(flag)
        if b is None:
            logger.error("Set save_rgb_img failed: illegal parameter")
            return not STORE_OK
        self.save_rgb_img = b
        logger.info("Set save_rgb_img successes: %s", b)
        return STORE_OK

    def set_save_ir_img(self, flag):
        """设置是否保存红外图像。"""
        b = coerce_bool(flag)
        if b is None:
            logger.error("Set save_ir_img failed: illegal parameter")
            return not STORE_OK
        self.save_ir_img = b
        logger.info("Set save_ir_img successes: %s", b)
        return STORE_OK

    def set_save_ir_temp(self, flag):
        """设置是否保存温度矩阵。"""
        b = coerce_bool(flag)
        if b is None:
            logger.error("Set save_ir_temp failed: illegal parameter")
            return not STORE_OK
        self.save_ir_temp = b
        logger.info("Set save_ir_temp successes: %s", b)
        return STORE_OK

    # ----------------------------- 文件读写 -----------------------------
    def load_param_from_file(self, config):
        """从 QSettings 读取参数。

        若任何参数非法, 回退默认并写回。
        Key 约定:
          STORE/PATH, STORE/SAVE_RGB_IMG, STORE/SAVE_IR_IMG, STORE/SAVE_IR_TEMP
        """
        # 若 config 不具备 value 方法，则直接失败
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
        """保存当前参数到 QSettings。"""
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
        """重置为默认并写入 QSettings。"""
        self._reset_param()
        logger.info("Reset store param successes")
        self.save_param_to_file(config)
        logger.info("Reset store param of file successes")
        return STORE_OK
