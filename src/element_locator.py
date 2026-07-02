"""元素定位模块 - XPath + 属性选择器定位

提供基于 uiautomator2 XPath 引擎的元素定位能力，
支持缓存、超时、回退策略。
"""

from typing import Optional
from dataclasses import dataclass

import uiautomator2 as u2
from loguru import logger


@dataclass
class ElementInfo:
    """元素信息"""
    text: str = ""
    resource_id: str = ""
    class_name: str = ""
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    visible: bool = False

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


class ElementLocator:
    """元素定位器

    封装 uiautomator2 的 XPath 和选择器 API。
    """

    def __init__(self, d: u2.Device):
        self.d = d
        self._locator_cache: dict[str, ElementInfo] = {}

    def find_by_text(self, text: str, timeout: float = 5.0) -> Optional[ElementInfo]:
        """通过文本内容查找元素

        Args:
            text: 目标文本（支持模糊匹配）
            timeout: 超时秒数

        Returns:
            ElementInfo 或 None
        """
        try:
            el = self.d.xpath(f'//*[@text="{text}"]').get(timeout=timeout)
            if el is None:
                return None
            return self._el_to_info(el)
        except Exception as e:
            logger.debug(f"find_by_text('{text}') 失败: {e}")
            return None

    def find_by_text_contains(self, text: str, timeout: float = 5.0) -> Optional[ElementInfo]:
        """通过包含文本查找元素"""
        try:
            el = self.d.xpath(f'//*[contains(@text, "{text}")]').get(timeout=timeout)
            if el is None:
                return None
            return self._el_to_info(el)
        except Exception as e:
            logger.debug(f"find_by_text_contains('{text}') 失败: {e}")
            return None

    def find_by_resource_id(self, rid: str, timeout: float = 5.0) -> Optional[ElementInfo]:
        """通过 resource-id 查找元素

        Args:
            rid: resource-id，例如 "cn.damai:id/buy_btn"
            timeout: 超时秒数
        """
        try:
            el = self.d(resourceId=rid).wait(timeout=timeout)
            if not el:
                return None
            info = self._el_to_info(el)
            return info
        except Exception as e:
            logger.debug(f"find_by_resource_id('{rid}') 失败: {e}")
            return None

    def find_by_xpath(self, xpath: str, timeout: float = 5.0) -> Optional[ElementInfo]:
        """通过 XPath 查找元素

        Args:
            xpath: XPath 表达式
            timeout: 超时秒数
        """
        try:
            el = self.d.xpath(xpath).get(timeout=timeout)
            if el is None:
                return None
            return self._el_to_info(el)
        except Exception as e:
            logger.debug(f"find_by_xpath('{xpath}') 失败: {e}")
            return None

    def find_checked(self, text: str, timeout: float = 3.0) -> Optional[ElementInfo]:
        """查找 CheckBox 元素"""
        return self.find_by_xpath(
            f'//*[@text="{text}" and @checked="false"]',
            timeout=timeout,
        )

    def wait_until_gone(self, text: str, timeout: float = 10.0) -> bool:
        """等待元素消失（如加载弹窗）

        Returns:
            True 如果元素已消失
        """
        try:
            self.d.xpath(f'//*[@text="{text}"]').wait_gone(timeout=timeout)
            return True
        except Exception:
            return False

    def click_if_exists(self, text: str, timeout: float = 2.0) -> bool:
        """如果元素存在则点击

        Returns:
            True 如果成功点击
        """
        try:
            el = self.find_by_text(text, timeout=timeout)
            if el:
                self.d.click(el.center[0], el.center[1])
                return True
            return False
        except Exception:
            return False

    def get_screen_size(self) -> tuple[int, int]:
        """获取屏幕尺寸"""
        return self.d.window_size()

    def get_current_activity(self) -> str:
        """获取当前 Activity"""
        return self.d.info.get("currentActivity", "")

    def _el_to_info(self, el) -> ElementInfo:
        """将 uiautomator2 元素对象转为 ElementInfo"""
        try:
            rect = el.rect
            info = ElementInfo(
                text=getattr(el, "text", "") or "",
                resource_id=getattr(el, "resourceId", "") or "",
                class_name=getattr(el, "className", "") or "",
                x=rect.get("x", 0) if isinstance(rect, dict) else rect[0],
                y=rect.get("y", 0) if isinstance(rect, dict) else rect[1],
                w=rect.get("width", 0) if isinstance(rect, dict) else rect[2],
                h=rect.get("height", 0) if isinstance(rect, dict) else rect[3],
            )
        except Exception:
            # fallback: 尝试 center 坐标
            cx, cy = el.center
            info = ElementInfo(x=cx, y=cy, w=1, h=1)
        return info

    def clear_cache(self):
        """清空定位缓存"""
        self._locator_cache.clear()
