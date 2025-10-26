"""
线程任务管理器

概述
----
提供两个基于 QThread 的通用工作线程：

- ``FunctionWorker``：一次性执行某个函数，并将结果/异常通过信号抛回 UI 线程。
- ``FunctionLoopWorker``：循环/长任务执行器（常用于实时任务），支持在任务内部通过 ``step`` 信号逐步上报进度或中间结果。

Notes
-----
- 该模块只负责线程封装与信号定义，不关心业务逻辑本身。
- 线程函数中若抛出异常，会由 ``error`` 信号通知 UI 线程，避免阻塞主界面。
"""

from PyQt5.QtCore import QObject, QThread, pyqtSignal


class WorkerSignals(QObject):
    """
    通用一次性任务的信号容器。

    Attributes
    ----------
    result : pyqtSignal
        任务执行成功时携带返回值发送（object）。
    error : pyqtSignal
        任务执行出现异常时发送（不携带异常对象，避免跨线程复杂对象传递）。
    """
    result = pyqtSignal(object)
    error = pyqtSignal()


class FunctionWorker(QThread):
    """
    一次性函数执行线程。

    Parameters
    ----------
    function : callable
        待执行的可调用对象。
    *args
        传递给可调用对象的位置参数。
    **kwargs
        传递给可调用对象的关键字参数。

    Notes
    -----
    在线程 ``run()`` 中调用 ``function``，结束后通过 ``signals.result`` 发射返回值；
    若出现异常，通过 ``signals.error`` 通知外部。
    """

    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.signals: WorkerSignals = WorkerSignals()
        self._function = function
        self._args = args
        self._kwargs = kwargs

    def run(self):
        """
        执行传入的函数并处理结果或异常。

        Returns
        -------
        None
        """
        try:
            result = self._function(*self._args, **self._kwargs)
            self.signals.result.emit(result)
        except:
            # 将异常吞掉并改为信号通知，避免线程崩溃影响 UI
            self.signals.error.emit()


class LoopWorkerSignals(QObject):
    """
    循环/长耗时任务专用的信号容器。支持进度/中间结果。

    Attributes
    ----------
    result : pyqtSignal
        任务最终结果。
    step : pyqtSignal
        任务中间进度或单步结果（object）。
    error : pyqtSignal
        任务运行异常。
    """
    result = pyqtSignal(object)
    step = pyqtSignal(object)
    error = pyqtSignal()


class FunctionLoopWorker(QThread):
    """
    可在内部周期性发射 ``step`` 的长任务执行线程。

    Parameters
    ----------
    function : callable
        业务函数，要求签名形如 ``func(step_signal, *args, **kwargs)``，其中 ``step_signal``
        即为 ``LoopWorkerSignals.step``。
    *args
        传递给业务函数的位置参数。
    **kwargs
        传递给业务函数的关键字参数。

    Notes
    -----
    - 任务结束时，函数返回一个最终结果对象，通过 ``signals.result`` 发出。
    - 异常通过 ``signals.error`` 通知。
    """

    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.signals: LoopWorkerSignals = LoopWorkerSignals()
        self._function = function
        self._args = args
        self._kwargs = kwargs

    def run(self):
        """
        执行传入函数，并将 ``step`` 信号透传给业务函数使用。

        Returns
        -------
        None
        """
        try:
            result = self._function(self.signals.step, *self._args, **self._kwargs)
            self.signals.result.emit(result)
        except:
            # 捕获异常并以信号形式上报
            self.signals.error.emit()