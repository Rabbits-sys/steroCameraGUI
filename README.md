# Stereo Camera GUI 工具

> 基于 PyQt5 与 qfluentwidgets 的可见光 + 红外相机采集与抓拍图形界面工具。
>
> 支持海康可见光相机与红外（Guide/SGP SDK）相机的登录、参数调节、取流显示、抓拍及多格式数据保存。

## ✨ 功能特性
- 可见光 (RGB) 相机
  - 枚举/选择设备
  - 打开 / 关闭
  - 连续取流显示（窗口句柄渲染）
  - 曝光时间 / 增益 / 帧率 调节
  - 单帧 JPG 抓拍
- 红外 (IR) 相机
  - 设备初始化 / 登录 / 登出
  - 红外视频取流（回调 → Qt 信号 → QLabel）
  - 伪彩色带开关与色表选择
  - 自动调焦
  - 热力图导出（JPEG）
  - 温度矩阵读取（JSON 保存）
- 存储管理
  - 自定义存储目录（默认 `records/`）
  - 可选保存：RGB 图像 / IR 图像 / 温度矩阵
  - 抓拍文件时间戳命名: `YYYYMMDDHHMMSS_[rgb|ir|temp.*]`
- 参数配置
  - 使用 `config.ini` 持久化（QSettings INI）
  - 参数非法时自动重置并提示
- 界面体验
  - 深色主题 (qfluentwidgets Theme.DARK)
  - 分段导航 + 卡片式设置 + 状态 Markdown 面板
  - 高 DPI 支持
- 日志
  - 运行日志写入 `program.log`

## 🗂 目录结构（节选）
```
├─ demo.py                # 应用入口
├─ config.ini             # 运行后生成/更新的参数配置文件
├─ storeManage.py         # 存储参数管理
├─ view/                  # UI 代码（.ui 转换 / 业务封装）
│  └─ home_interface.py   # 主界面聚合
├─ driver/
│  ├─ hikDriver.py        # 海康 RGB 相机封装
│  ├─ guideDriver.py      # 红外相机封装（SGP SDK）
│  └─ hikrobot/|guide/    # SDK 二次封装与常量
├─ sdk/                   # 第三方 DLL / 日志配置等
├─ records/               # 抓拍/采集输出目录（运行时生成）
├─ resource/              # 图标 / 界面资源
└─ README.md
```

## 🔧 运行环境
- 操作系统：Windows (建议 64-bit)
- Python：3.7+（PyQt5 与部分旧版 SDK 兼容性更佳）
- 依赖：`PyQt5`, `qfluentwidgets`
- 驱动：海康 MVS / Guide SGP SDK （对应 DLL 已放入 `sdk/`）

## 📦 安装步骤
```cmd
# 1. （可选）创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 2. 安装依赖（若你创建了 requirements.txt，可执行）
pip install PyQt5 qfluentwidgets

# 3. 运行
python demo.py
```

> 如果需要在任意目录启动，确保将 `sdk/` 目录下的 DLL 所在路径加入 `PATH`（或与 `demo.py` 同目录）。

## ⚙️ 配置文件 `config.ini`
应用运行后自动生成，可手动编辑。示例：
```ini
[GUIDE]
SERVER=192.168.1.168
USERNAME=admin
PASSWORD=admin123
PORT=80

[STORE]
PATH=D:\\WorkSpaces\\QtProjects\\steroCameraGUI\\records
SAVE_RGB_IMG=1
SAVE_IR_IMG=1
SAVE_IR_TEMP=1
```
字段说明：
- GUIDE/SERVER, PORT, USERNAME, PASSWORD：红外相机登录参数
- STORE/PATH：存储目录（不存在会自动创建）
- STORE/SAVE_*：是否保存对应数据 (0/1)

> 若值非法，程序会回退默认并弹出提示 InfoBar。

## 🖥 使用流程
1. 启动程序，等待 SplashScreen 结束。
2. 在 “可见光相机” 页：
   - 点击 “遍历” → 选择设备 → “打开设备”
   - 调整曝光 / 增益 / 帧率（开机后可用）
3. 在 “红外相机” 页：
   - 输入 IP/端口/用户名/密码 → “登录设备”
   - 可开关色带、修改伪彩映射编号、自动调焦
4. 在 “采集设置” 页：
   - 选择存储目录
   - 勾选需要保存的类型
5. 回到状态卡片：
   - 点击 “开始采样” 开启流（支持仅开单个或两个相机）
   - 点击 “抓拍” 保存勾选类型文件
   - 点击 “结束采样” 停止
6. 抓拍结果位于 `records/`（或自定义目录）

## 💾 数据命名与格式
- RGB 图像：`YYYYMMDDHHMMSS_rgb.jpg`
- IR 伪彩图：`YYYYMMDDHHMMSS_ir.jpg`
- IR 温度矩阵：`YYYYMMDDHHMMSS_temp.json`（线性一维数组，长度 = 分辨率像素数）

## 🛠 主要类概览
| 模块 | 类 | 说明 |
|------|----|------|
| `view/home_interface.py` | `HomeInterface` | 主界面容器与子界面调度 |
| `driver/hikDriver.py` | `RGBCamera` | 海康相机封装（枚举/开关/取流/参数/抓拍） |
| `driver/guideDriver.py` | `IRCamera` | 红外相机封装（登录/视频/测温/抓拍/参数） |
| `storeManage.py` | `StoreManage` | 存储目录与保存选项管理 |

## 🧪 可靠性与错误处理
- 所有驱动层方法返回整型状态码（0 成功 / 非 0 失败），不抛异常 → GUI 层用 InfoBar 提示。
- 资源释放：
  - 退出时若仍在取流/登录，会在析构中尝试关闭。
- 非法参数处理：
  - 相机参数越界 → 记录日志 + 返回错误码
  - 配置文件值异常 → 重置默认 + 弹出警告

## ❓ 常见问题 (FAQ)
| 问题         | 可能原因              | 解决建议                     |
|------------|-------------------|--------------------------|
| 无法枚举到 RGB 设备 | 未安装海康 MVS / 驱动冲突  | 安装官方 SDK，重启程序与设备         |
| 红外登录失败     | IP/端口/账号错误 / 设备离线 | 确认网络连通 & 账号密码            |
| 温度矩阵长度不对   | 分辨率与期望不一致         | 确认设备输出尺寸（示例中使用 384×512）  |
| 图像抓取失败     | 路径存在中文            | 删除 config.ini 后在纯英文路径下运行 |

## 📝 日志
- 默认写入：`program.log`
- 驱动/参数错误会追加到日志，便于排查。

## 🔐 许可证
本项目采用 [MIT License](./LICENSE)。

## 🙏 致谢
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- [qfluentwidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
- 海康威视 MVS SDK
- Guide / SGP 红外相机 SDK

## 🧩 后续可拓展方向
- 增加批量定时采集策略
- 引入多线程/异步保存以减少 UI 阻塞
- 提供温度矩阵 → 伪彩 PNG 直接渲染
- 增加单元测试（StoreManage / 参数校验）

---
若你在使用过程中遇到问题或需要新功能，欢迎提交 Issue 或 PR。

