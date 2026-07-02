"""图像兜底模块

当 XPath 定位失败时，使用 AirTest 图像模板匹配兜底。
适用于大麦 App 动态渲染、自定义 View 导致 XPath 失效的场景。
"""

from pathlib import Path
from typing import Optional

import uiautomator2 as u2
from loguru import logger


class ImageFallback:
    """图像模板匹配兜底

    预热阶段为关键按钮截图保存模板。
    冲刺阶段当盲点 / XPath 都失败时，用模板匹配定位点击。

    Usage:
        fb = ImageFallback(d, "templates")
        fb.record_template("buy_btn", "//*[@text='立即购票']")
        fb.touch_by_template("buy_btn")
    """

    def __init__(self, d: u2.Device, tpl_dir: str = "templates"):
        self.d = d
        self.tpl_dir = Path(tpl_dir)
        self.tpl_dir.mkdir(parents=True, exist_ok=True)
        self._template_registry: dict[str, str] = {}  # name -> path

    def record_template(self, button_name: str, xpath_expr: str) -> bool:
        """预热阶段通过 XPath 找到目标区域，截图保存为模板

        Args:
            button_name: 按钮别名
            xpath_expr: XPath 表达式

        Returns:
            True 如果模板保存成功
        """
        try:
            el = self.d.xpath(xpath_expr).get(timeout=5)
            if el is None:
                logger.warning(f"模板记录失败: 未找到 {button_name}")
                return False

            rect = el.rect
            if isinstance(rect, dict):
                lx, ly, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
            else:
                lx, ly, w, h = rect

            # 截图整个屏幕
            screen = self.d.screenshot(format="pillow")
            if screen is None:
                logger.warning("截图失败")
                return False

            # 裁剪目标区域（向外扩展 10px 增加容错）
            pad = 10
            crop_box = (
                max(0, lx - pad),
                max(0, ly - pad),
                min(screen.width, lx + w + pad),
                min(screen.height, ly + h + pad),
            )
            cropped = screen.crop(crop_box)
            tpl_path = self.tpl_dir / f"{button_name}.png"
            cropped.save(str(tpl_path))
            self._template_registry[button_name] = str(tpl_path)
            logger.info(f"模板保存: {button_name} → {tpl_path} (区域: {crop_box})")
            return True
        except Exception as e:
            logger.warning(f"模板记录失败 {button_name}: {e}")
            return False

    def touch_by_template(self, button_name: str, threshold: float = 0.8) -> bool:
        """通过截图模板匹配点击

        Args:
            button_name: 按钮别名
            threshold: 匹配阈值 0.0-1.0，越高越严格

        Returns:
            True 如果成功点击
        """
        tpl_path = self._template_registry.get(button_name)
        if not tpl_path or not Path(tpl_path).exists():
            logger.warning(f"模板不存在: {button_name}")
            return False

        try:
            from airtest.core.api import Template, touch

            tpl = Template(tpl_path, threshold=threshold)
            pos = touch(tpl)
            logger.info(f"图像点击成功: {button_name} @ {pos}")
            return True
        except Exception as e:
            logger.warning(f"图像点击失败 {button_name}: {e}")
            return False

    def has_template(self, button_name: str) -> bool:
        """检查模板是否存在"""
        return button_name in self._template_registry
