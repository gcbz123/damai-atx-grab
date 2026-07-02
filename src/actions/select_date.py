"""日期选择操作模块

大麦 App 日期选择方式：
  1. 横向 ScrollView 滑动
  2. 找到目标日期文本并点击
"""

from loguru import logger
import uiautomator2 as u2


def select_date(d: u2.Device, date_text: str, timeout: float = 5.0) -> bool:
    """选择演出日期

    大麦的日期栏是横向滚动的 RecyclerView/ScrollView。
    策略：先尝试直接查找，找不到则横向滑动后重试。

    Args:
        d: uiautomator2 设备实例
        date_text: 日期文本（如 "12.06"、"周六"）
        timeout: 超时秒数

    Returns:
        True 如果日期选择成功
    """
    logger.info(f"开始选择日期: {date_text}")

    try:
        # 1. 先尝试直接查找
        date_el = d.xpath(f'//*[@text="{date_text}"]').get(timeout=3)
        if date_el:
            date_el.click()
            logger.info(f"日期选择成功: {date_text}")
            return True
    except Exception:
        pass

    # 2. 横向滑动后查找（最多滑动 3 次）
    w, h = d.window_size()
    for i in range(3):
        try:
            # 从右向左滑动
            d.swipe(w * 0.85, h * 0.3, w * 0.15, h * 0.3, duration=0.2)
            logger.debug(f"日期栏滑动第 {i + 1} 次")

            date_el = d.xpath(f'//*[@text="{date_text}"]').get(timeout=2)
            if date_el:
                date_el.click()
                logger.info(f"日期选择成功: {date_text}")
                return True
        except Exception:
            continue

    logger.warning(f"日期选择失败: {date_text}")
    return False
