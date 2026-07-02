"""票价选择操作模块

票价选择策略：
  1. 按文本匹配票价名称
  2. 文本匹配失败时按列表索引兜底
"""

from loguru import logger
import uiautomator2 as u2


def select_price(
    d: u2.Device,
    price_text: str,
    price_index: int = 0,
    timeout: float = 5.0,
) -> bool:
    """选择票价档位

    Args:
        d: uiautomator2 设备实例
        price_text: 票价文本（如 "内场1199元"）
        price_index: 索引兜底（从 0 开始）
        timeout: 超时秒数

    Returns:
        True 如果票价选择成功
    """
    logger.info(f"开始选择票价: {price_text}")

    try:
        # 1. 优先文本匹配
        price_el = d.xpath(f'//*[@text="{price_text}"]').get(timeout=timeout)
        if price_el:
            price_el.click()
            logger.info(f"票价选择成功（文本匹配）: {price_text}")
            return True
    except Exception:
        pass

    # 2. 文本包含匹配
    try:
        price_el = d.xpath(
            f'//*[contains(@text, "{price_text}")]'
        ).get(timeout=3)
        if price_el:
            price_el.click()
            logger.info(f"票价选择成功（包含匹配）: {price_text}")
            return True
    except Exception:
        pass

    # 3. 索引兜底（选中列表中第 N 个可选票价）
    try:
        price_list = d.xpath(
            "//android.widget.LinearLayout//*[@clickable='true']"
        ).all()
        if price_list and len(price_list) > price_index:
            price_list[price_index].click()
            logger.info(f"票价选择成功（索引 {price_index}）")
            return True
    except Exception as e:
        logger.warning(f"票价索引选择失败: {e}")

    logger.warning(f"票价选择失败: {price_text}")
    return False
