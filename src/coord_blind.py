"""坐标盲点点击模块 —— 性能核心

预热阶段通过 XPath 记录按钮坐标，冲刺阶段直接用 d.click(x, y)
跳过元素查找，实现 1-5ms 单次点击。

优化:
  - 增加坐标漂移检测（页面滚动后坐标可能偏移）
  - 失败重试时自动偏移补偿（±5px）
"""

from typing import Optional
import uiautomator2 as u2
from loguru import logger


class CoordBlindClicker:
    """坐标盲点点击器

    预热时记录按钮坐标 -> 冲刺时盲点点击。
    支持自动降级：盲点连续失败 → 回退 XPath → 重新校准坐标。
    支持坐标漂移补偿：连续失败时自动微调坐标重试。

    Usage:
        clicker = CoordBlindClicker(d)
        # 预热阶段
        clicker.record_coord('buy_btn', '//*[@text="立即购票"]')
        # 冲刺阶段
        clicker.blind_click('buy_btn')
    """

    def __init__(self, d: u2.Device):
        self.d = d
        # 按钮名 → (x, y)
        self.coord_cache: dict[str, tuple[int, int]] = {}
        # 按钮名 → xpath 表达式（降级用）
        self.xpath_cache: dict[str, str] = {}
        # 连续失败计数
        self._consecutive_failures: dict[str, int] = {}
        # 漂移补偿步长（像素）
        self._drift_step = 5
        self.max_fallbacks = 3  # 连续失败几次后降级

    def record_coord(self, button_name: str, xpath_expr: str) -> bool:
        """预热阶段通过 XPath 记录按钮坐标

        Args:
            button_name: 按钮别名（如 'buy_btn'）
            xpath_expr: XPath 表达式

        Returns:
            True 如果坐标记录成功
        """
        try:
            el = self.d.xpath(xpath_expr).get(timeout=5)
            if el is None:
                logger.warning(f"坐标记录失败: 未找到 {button_name} ({xpath_expr})")
                return False
            cx, cy = el.center
            self.coord_cache[button_name] = (cx, cy)
            self.xpath_cache[button_name] = xpath_expr
            self._consecutive_failures[button_name] = 0
            logger.info(f"坐标记录: {button_name} → ({cx}, {cy})")
            return True
        except Exception as e:
            logger.warning(f"坐标记录失败 {button_name}: {e}")
            return False

    def blind_click(self, button_name: str) -> bool:
        """冲刺阶段直接 d.click() 坐标注入，单次 1-5ms

        优化：增加坐标漂移补偿 — 连续失败时自动微调坐标重试。

        Args:
            button_name: 按钮别名

        Returns:
            True 如果点击成功
        """
        if button_name not in self.coord_cache:
            logger.warning(f"盲点点击失败: {button_name} 未缓存坐标")
            return self.fallback_click(button_name)

        x, y = self.coord_cache[button_name]
        failures = self._consecutive_failures.get(button_name, 0)

        try:
            # 如果有连续失败，尝试漂移补偿（最多 ±15px）
            if failures > 0:
                offset = self._drift_step * min(failures, 3)
                # 交替尝试不同方向
                if failures % 2 == 1:
                    x += offset
                else:
                    x -= offset
                if failures % 3 == 0:
                    y += self._drift_step
                else:
                    y -= self._drift_step

            self.d.click(x, y)
            self._consecutive_failures[button_name] = 0
            return True
        except Exception as e:
            logger.debug(f"盲点点击失败 {button_name} @ ({x},{y}): {e}")
            self._consecutive_failures[button_name] = failures + 1
            # 连续失败超过阈值 → 降级到 XPath
            if self._consecutive_failures[button_name] >= self.max_fallbacks:
                logger.warning(f"{button_name} 连续 {self.max_fallbacks} 次失败，降级到 XPath")
                return self.fallback_click(button_name)
            return False

    def fallback_click(self, button_name: str) -> bool:
        """坐标失败时回退到 XPath 查找点击，并重新校准坐标

        Args:
            button_name: 按钮别名

        Returns:
            True 如果降级点击成功
        """
        xpath = self.xpath_cache.get(button_name)
        if not xpath:
            logger.error(f"降级失败: {button_name} 无 xpath 记录")
            return False

        try:
            el = self.d.xpath(xpath).get(timeout=3)
            if el is None:
                return False
            self.d.xpath(xpath).click(timeout=2)
            # 重新校准坐标
            cx, cy = el.center
            self.coord_cache[button_name] = (cx, cy)
            self._consecutive_failures[button_name] = 0
            logger.info(f"降级点击成功: {button_name} 坐标已校准 → ({cx}, {cy})")
            return True
        except Exception as e:
            logger.warning(f"降级点击失败 {button_name}: {e}")
            return False

    def get_coord(self, button_name: str) -> Optional[tuple[int, int]]:
        """获取缓存的按钮坐标"""
        return self.coord_cache.get(button_name)

    def has_coord(self, button_name: str) -> bool:
        """检查按钮坐标是否已缓存"""
        return button_name in self.coord_cache

    def clear_cache(self):
        """清空所有缓存"""
        self.coord_cache.clear()
        self.xpath_cache.clear()
        self._consecutive_failures.clear()
