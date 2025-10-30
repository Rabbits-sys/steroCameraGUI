import json
import os
import glob
import logging
from PyQt5.QtGui import QImage

logger = logging.getLogger(__name__)

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
        logger.info("Choose rendering single JSON file")
        dir = os.path.dirname(path)

    elif os.path.isdir(path):
        logger.info(f"Choose rendering all JSON files in the directory {path}")
        dir = path

    ir_temp_dict = load_ir_temp(path)
    count = 0
    if ir_temp_dict:
        for filename, ir_temp in ir_temp_dict.items():

            output_path = dir + '/' + filename + '.jpg'
            save_ir_img(output_path, ir_temp, height, width)
            count += 1
            progress_value = int(count  / len(ir_temp_dict) * 100)

            progress_info = {
                'message': f'已处理：{filename}.json',
                'output_path': output_path,
                'count ': count,
                'progress_value': progress_value,
            }
            step_signal.emit(progress_info)

        last_image = QImage(output_path)
        result = {
            'message': f'完成{count}个温度矩阵的渲染',
            'count': count,
            'last_image' : last_image
        }
        return result
    else:
        result = {
        'message': f'无JSON文件',
        'count': count,
        }
        return result

def load_ir_temp(path):
    """加载温度矩阵

    Parameters
    ----------
    path : str
        文件或文件夹路径。

    Returns
    -------
    dict[str, list] | None
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
        logger.error(f"无JSON文件")
        return None

    for file_path in json_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 获取文件名（不含路径和扩展名）
        filename = os.path.splitext(os.path.basename(file_path))[0]
        ir_temp_dict[filename] = data
        logger.info(f"Read file Successfully: {filename}.json")

    return ir_temp_dict

def save_ir_img(path, data, height=384 , width=512):
    """将温度矩阵渲染为灰度图像并保存

    Parameters
    ----------
    path : str
        文件路径。
    data : list
        温度矩阵。
    height : int , default=384
        目标图像的高。
    Width : int , default=512
        目标图像的宽。

    """
    if len(data) != height * width:
        logger.error(f"Data size mismatch")

    # 归一化到0-255范围
    data_normalized = normalize(data)

    # reshape为目标形状
    array = []
    for i in range(height):
        start = i * width
        end = start + width
        array.append(data_normalized[start:end])

    # 保存图像
    buf = bytes([array[y][x] for y in range(height) for x in range(width) for _ in range(3)])
    image = QImage(buf, width, height, width * 3, QImage.Format_RGB888).copy()

    image.save(path)
    logger.info(f"Render and save successfully: {path}")

def find_min_max(data):
    """求一维列表的最小值和最大值"""
    if not data:
        return None, None

    min_val = max_val = data[0]

    for num in data[1:]:
        if num < min_val:
            min_val = num
        elif num > max_val:
            max_val = num

    return min_val, max_val

def normalize(data):
    """列表的广播运算"""
    min, max = find_min_max(data)
    return [int((x - min)/(max - min + 1e-16) * 255) for x in data]