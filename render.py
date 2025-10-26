import json
import numpy as np
import os
import glob
from PIL import Image
from PyQt5.QtGui import QImage

def render_temp2img(step_signal, path, height=384, width=512):
    """
    红外温度矩阵渲染主流程：先加载温度矩阵，保存为字典，再将每个json文件对应的numpy数组渲染为红外图像

    Parameters
    ----------
    step_signal :
    path : str
        文件或文件夹路径。
    """
    if os.path.isfile(path):
        print('单个JSON文件渲染')
        dir = os.path.dirname(path)

    elif os.path.isdir(path):
        print(f"{path}目录下所有JSON文件渲染")
        dir = path

    ir_temp_dict = load_ir_temp(path)
    sum = len(ir_temp_dict)
    output_path = ''
    if ir_temp_dict:
        count  = 0
        for filename, ir_temp in ir_temp_dict.items():

            output_path = dir + '/' + filename + '.jpg'
            save_ir_img(output_path, ir_temp, height, width)
            count += 1
            progress_value = int(count  / sum * 100)

            progress_info = {
                'message': f'已处理：{filename}.json',
                'output_path': output_path,
                'count ': count,
                'progress_value': progress_value,
            }
            step_signal.emit(progress_info)
            # step_signal.emit(progress_value)

        last_image = QImage(output_path)
        result = {
            'message': f'完成{sum}个温度矩阵的渲染',
            'sum ': sum,
            'last_image' : last_image
        }
        return result
    return None

def load_ir_temp(path):
    """加载温度矩阵

    Parameters
    ----------
    path : str
        文件或文件夹路径。

    Returns
    -------
    dict[str, numpy.ndarray[float]] | None
        字典，键为文件名，值为温度矩阵。若无json文件，则返回None
    """

    ir_temp_dict = {}
    json_files = []

    if os.path.isfile(path):
        json_files.append(path)

    elif os.path.isdir(path):
        folder_path = path
        # 使用glob查找所有json文件
        json_files = glob.glob(os.path.join(folder_path, "*.json"))

    if not json_files:
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

def save_ir_img(path, data, height=384 , width=512):
    """将温度矩阵渲染为灰度图像并保存

    Parameters
    ----------
    path : str
        文件路径。
    data : numpy.ndarray[float]
        温度矩阵。
    height : int , default=384
        目标图像的高。
    Width : int , default=512
        目标图像的宽。

    """
    # reshape为目标形状
    reshaped_array = data.reshape(height, width)

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