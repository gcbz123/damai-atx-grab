"""城市选择操作模块

大麦 App 城市切换：
  1. 点击当前城市按钮
  2. 弹城市列表 → 滚动查找目标城市 → 点击
"""

from loguru import logger
import uiautomator2 as u2


def select_city(d: u2.Device, city_name: str, timeout: float = 10.0) -> bool:
    """切换大麦 App 的目标城市

    Args:
        d: uiautomator2 设备实例
        city_name: 目标城市名（如 "深圳"）
        timeout: 超时秒数

    Returns:
        True 如果城市选择成功
    """
    logger.info(f"开始选择城市: {city_name}")

    try:
        # 1. 点击当前城市按钮（通常在页面顶部）
        city_btn = d.xpath("//*[@resource-id='cn.damai:id/city_item']").get(timeout=3)
        if city_btn:
            city_btn.click()
            logger.debug("点击城市按钮")
        else:
            # 兜底：找包含"城市"文本的按钮
            d.xpath("城市").click(timeout=3)
    except Exception as e:
        logger.warning(f"点击城市按钮失败: {e}")
        # 如果已经在城市列表页，直接继续

    try:
        # 2. 搜索城市（如果有搜索框）
        search_input = d.xpath(
            "//android.widget.EditText"
        ).get(timeout=2)
        if search_input:
            search_input.set_text(city_name)
            logger.debug(f"搜索框输入: {city_name}")
        else:
            # 3. 没有搜索框 → 滚动查找
            d.xpath(city_name).click(timeout=timeout)
            logger.info(f"城市选择成功: {city_name}")
            return True

        # 4. 等待搜索结果并点击
        d.xpath(f'//*[@text="{city_name}"]').click(timeout=timeout)
        logger.info(f"城市选择成功: {city_name}")
        return True

    except Exception as e:
        logger.error(f"城市选择失败: {e}")
        return False
