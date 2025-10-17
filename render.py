import json
import numpy as np
import os
import glob
from PIL import Image

def load_single_ir_temp(file_path):
    """加载单个温度矩阵

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

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 转换为numpy数组
    array = np.array(data)

    # 获取文件名（不含路径和扩展名）
    filename = os.path.splitext(os.path.basename(file_path))[0]
    ir_temp_dict[filename] = array

    print(f"成功读取: {filename} -> 形状: {array.shape}")

    return ir_temp_dict

def load_all_ir_temp(folder_path):
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


def save_ir_img(path, data, hight=384 , Width=512):
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
    # print(f"图像已保存为: "+ path)


if __name__ == '__main__':
    folder_path = "records"
    ir_temp_dict = load_all_ir_temp(folder_path)
    for filename, ir_temp in ir_temp_dict.items():
        output_path = folder_path + filename + '.jpg'
        print(output_path)
        save_ir_img(output_path,ir_temp)

