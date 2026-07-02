"""极速冲刺引擎

开售瞬间以最小间隔循环点击购买/确认按钮。
参考 HaTickets / damai-ticket-fenter-app 的最优实践。

性能指标:
  - 单次盲点点击: 1-5ms
  - 循环间隔: 50ms（可配置）
  - 页面跳转检测: 5-15ms/次（Activity 检测）
  - 降级到 XPath 查找: 10-50ms
"""

import time
from typing import Callable, Optional

import uiautomator2 as u2
from loguru import logger

from src.coord_blind import CoordBlindClicker
from src.element_locator import ElementLocator


class SprintEngine:
    """极速冲刺引擎

    在开售瞬间以毫秒级间隔循环点击购票/确认/提交按钮。
    冲刺阶段不做元素查找，仅坐标盲点点击。

    Usage:
        engine = SprintEngine(d, clicker)
        engine.sprint_buy(target_timestamp, interval_ms=50)
    """

    def __init__(
        self,
        d: u2.Device,
        clicker: CoordBlindClicker,
        locator: Optional[ElementLocator] = None,
    ):
        self.d = d
        self.clicker = clicker
        self.locator = locator or ElementLocator(d)
        self._start_time = 0.0
        self._click_count = 0
        self._page_changed = False

    def sprint_buy(
        self,
        target_time_ms: int,
        interval_ms: int = 50,
        max_retries: int = 60,
    ) -> bool:
        """开售瞬间开始循环点击「立即购票」按钮

        Args:
            target_time_ms: 开售时间戳（毫秒）
            interval_ms: 循环间隔（默认 50ms）
            max_retries: 最大重试次数

        Returns:
            True 如果检测到页面跳转（进入票档页）
        """
        logger.info(f"🚀 冲刺购票开始 | 间隔={interval_ms}ms | 最大重试={max_retries}")

        self._start_time = time.time()
        self._click_count = 0
        self._page_changed = False

        # 等待目标时刻
        now = int(time.time() * 1000)
        wait_ms = target_time_ms - now
        if wait_ms > 0:
            logger.debug(f"等待开售: {wait_ms}ms")
            while int(time.time() * 1000) < target_time_ms:
                pass  # CPU 自旋

        # 冲刺循环
        for i in range(max_retries):
            self.clicker.blind_click('buy_btn')
            self._click_count += 1

            # 检测页面是否变化
            if self._check_page_changed(expected_not_contains='detail'):
                elapsed = (time.time() - self._start_time) * 1000
                logger.info(
                    f"✅ 购票页面跳转成功！"
                    f"点击 {self._click_count} 次, 耗时 {elapsed:.0f}ms"
                )
                self._page_changed = True
                return True

            # 间隔等待
            if interval_ms > 0:
                self._wait_interval(interval_ms)

        elapsed = (time.time() - self._start_time) * 1000
        logger.warning(f"⚠️ 购票冲刺超时: {self._click_count} 次, {elapsed:.0f}ms")
        return False

    def sprint_confirm(
        self,
        interval_ms: int = 50,
        max_retries: int = 30,
    ) -> bool:
        """在确认页循环点击「确认」按钮

        用于选票后确认票档、数量、观演人。

        Args:
            interval_ms: 循环间隔
            max_retries: 最大重试次数

        Returns:
            True 如果进入提交页
        """
        logger.info(f"🚀 冲刺确认开始 | 间隔={interval_ms}ms")

        for i in range(max_retries):
            self.clicker.blind_click('confirm_btn')
            self._click_count += 1

            if self._check_page_changed(expected_contains='order'):
                logger.info(f"✅ 确认页跳转成功！共点击 {self._click_count} 次")
                self._page_changed = True
                return True

            if interval_ms > 0:
                self._wait_interval(interval_ms)

        logger.warning("⚠️ 确认冲刺超时")
        return False

    def sprint_submit(
        self,
        interval_ms: int = 50,
        max_retries: int = 30,
    ) -> bool:
        """在提交页循环点击「立即提交」按钮

        Args:
            interval_ms: 循环间隔
            max_retries: 最大重试次数

        Returns:
            True 如果进入付款页
        """
        logger.info(f"🚀 冲刺提交开始 | 间隔={interval_ms}ms")

        for i in range(max_retries):
            self.clicker.blind_click('submit_btn')
            self._click_count += 1

            if self._check_page_changed(expected_contains='pay'):
                logger.info(f"✅ 提交成功！进入付款页！共点击 {self._click_count} 次")
                self._page_changed = True
                return True

            if interval_ms > 0:
                self._wait_interval(interval_ms)

        logger.warning("⚠️ 提交冲刺超时")
        return False

    def _check_page_changed(
        self,
        expected_not_contains: str = "",
        expected_contains: str = "",
    ) -> bool:
        """检测页面是否变化

        通过 Activity 检测比元素查找快 10 倍。

        Args:
            expected_not_contains: 当前页面不应包含的文本
            expected_contains: 目标页面应包含的文本

        Returns:
            True 如果页面已变化
        """
        try:
            activity = self.d.info.get("currentActivity", "")
            activity_lower = activity.lower()

            if expected_contains and expected_contains in activity_lower:
                return True
            if expected_not_contains and expected_not_contains not in activity_lower:
                return True
            return False
        except Exception:
            return False

    def _wait_interval(self, interval_ms: int):
        """精确等待间隔时间"""
        if interval_ms < 15:
            # 小间隔用 CPU 自旋
            target = time.perf_counter() + interval_ms / 1000
            while time.perf_counter() < target:
                pass
        else:
            time.sleep(interval_ms / 1000)

    @property
    def stats(self) -> dict:
        """返回本次冲刺统计信息"""
        elapsed = (time.time() - self._start_time) * 1000 if self._start_time else 0
        return {
            "click_count": self._click_count,
            "elapsed_ms": elapsed,
            "page_changed": self._page_changed,
        }
