import json
import numpy as np
import os
import glob
from PIL import Image
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtGui import QImage
from qfluentwidgets import InfoBar, InfoBarPosition

import time

# 通过.start()方法通知 cpu 有空就来执行线程对象的.run()方法
class RenderThread(QThread):

    sigSetProgress = pyqtSignal(int) # 进度条信号
    sigShowIrImage = pyqtSignal(QImage) # 图像显示信号
    sigTaskFinished = pyqtSignal(str,int) # 渲染任务结束信号，区分于线程结束信号.finished(不包含任何自定义数据)

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.render_num = 0

    def run(self):
        self.sigSetProgress.emit(0)

        if os.path.isfile(self.path):
            print('单个JSON文件渲染')
            dir = os.path.dirname(self.path)
            ir_temp_dict = self.load_single_ir_temp(self.path)
            if ir_temp_dict:
                for filename, ir_temp in ir_temp_dict.items():
                    output_path = dir + '/' + filename + '.jpg'
                    self.save_ir_img(output_path, ir_temp)
                    self.render_num = 1
                    image = QImage(output_path)
                    self.sigSetProgress.emit(100)
                    self.sigShowIrImage.emit(image)
            self.sigTaskFinished.emit(self.path,self.render_num)

        elif os.path.isdir(self.path):
            print(f"{self.path}目录下所有JSON文件渲染")
            ir_temp_dict = self.load_all_ir_temp(self.path)
            if ir_temp_dict:
                for filename, ir_temp in ir_temp_dict.items():
                    output_path = self.path + '/' + filename + '.jpg'
                    self.save_ir_img(output_path, ir_temp)
                    self.render_num += 1
                    self.sigSetProgress.emit(int(self.render_num / len(ir_temp_dict) * 100))
            self.sigTaskFinished.emit(self.path, self.render_num)

    def stop(self):
        self.requestInterruption()
        self.wait()  # 可选：等待线程真正结束

    def load_single_ir_temp(self, file_path):
        """加载单个温度矩阵

        Parameters
        ----------
        file_path : str
            文件路径。

        Returns
        -------
        dict[str, numpy.ndarray[float]] | None
            字典，键为文件名，值为温度矩阵。若无json文件，则返回None

        """

        ir_temp_dict = {}

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not data:
            return None

        # 转换为numpy数组
        array = np.array(data)

        # 获取文件名（不含路径和扩展名）
        filename = os.path.splitext(os.path.basename(file_path))[0]
        ir_temp_dict[filename] = array

        print(f"成功读取: {filename} -> 形状: {array.shape}")

        return ir_temp_dict

    def load_all_ir_temp(self, folder_path):
        """批量加载温度矩阵

        Parameters
        ----------
        folder_path : str
            文件夹路径。

        Returns
        -------
        dict[str, numpy.ndarray[float]] | None
            字典，键为文件名，值为温度矩阵。若无json文件，则返回None
        """

        ir_temp_dict = {}

        # 使用glob查找所有json文件
        json_files = glob.glob(os.path.join(folder_path, "*.json"))

        if not json_files:
            print(f"在文件夹 {folder_path} 中未找到JSON文件")
            return None

        for file_path in json_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 转换为numpy数组
            array = np.array(data)

            # 获取文件名（不含路径和扩展名）
            filename = os.path.splitext(os.path.basename(file_path))[0]
            ir_temp_dict[filename] = array

            print(f"成功读取: {filename} -> 形状: {array.shape}")

        return ir_temp_dict
        # return ir_temp_dict.values()

    def save_ir_img(self, path, data, hight=384, Width=512):
        """将温度矩阵渲染为灰度图像并保存

        Parameters
        ----------
        path : str
            文件路径。
        data : numpy.ndarray[float]
            温度矩阵。
        hight : int , default=384
            目标图像的高。
        Width : int , default=512
            目标图像的宽。

        """
        # reshape为目标形状
        reshaped_array = data.reshape(hight, Width)

        # 归一化到0-255范围
        if reshaped_array.dtype != np.uint8:
            normalized = (reshaped_array - reshaped_array.min()) / (reshaped_array.max() - reshaped_array.min() + 1e-16)
            image_data = (normalized * 255).astype(np.uint8)
        else:
            image_data = reshaped_array

        # 保存图像
        image = Image.fromarray(image_data)
        image.save(path)
        print(f"成功渲染并保存：{path}")

if __name__ == '__main__':
    folder_path = "records"
    #folder_path = os.path.join(os.getcwd(), 'records')
    renderThread = RenderThread(folder_path)
    start_time = time.time()
    renderThread.start()
    # 等待
    renderThread.wait(5000)  # 最多等待5秒
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"线程测试结束,运行时间:{elapsed_time}")





