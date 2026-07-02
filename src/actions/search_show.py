"""演出搜索 / 导航操作模块

通过以下方式进入目标演出详情页：
  1. item_url: 直接打开大麦商品链接（H5 → App 跳转）
  2. keyword: 搜索关键词 → 结果列表 → 点击进入
  3. 自动导航从首页进入目标演出
"""

from loguru import logger
import uiautomator2 as u2


def open_by_url(d: u2.Device, url: str) -> bool:
    """通过 URL 打开演出详情页

    大麦 App 支持通过 H5 链接唤起 App 详情页。

    Args:
        d: uiautomator2 设备实例
        url: 商品链接

    Returns:
        True 如果链接处理成功
    """
    logger.info(f"通过 URL 打开演出: {url}")
    try:
        # 使用 adb 打开 URL（Android 会唤起对应 App）
        d.app_open(url)
        logger.info("URL 跳转成功")
        return True
    except Exception as e:
        logger.error(f"URL 跳转失败: {e}")
        return False


def search_by_keyword(
    d: u2.Device,
    keyword: str,
    result_index: int = 0,
    timeout: float = 10.0,
) -> bool:
    """通过搜索关键词进入演出

    Args:
        d: uiautomator2 设备实例
        keyword: 搜索关键词（如 "刘若英 演唱会"）
        result_index: 搜索结果列表中点击第几个（默认第一个）
        timeout: 超时秒数

    Returns:
        True 如果成功进入演出详情页
    """
    logger.info(f"搜索演出: {keyword}")

    try:
        # 1. 点击搜索框
        search_icon = d.xpath("//*[@resource-id='cn.damai:id/search_icon']").get(
            timeout=3
        )
        if search_icon:
            search_icon.click()
            logger.debug("点击搜索图标")
        else:
            d.xpath("//*[@text='搜索']").click(timeout=3)
    except Exception as e:
        logger.warning(f"点击搜索入口失败: {e}")

    try:
        # 2. 输入关键词
        search_input = d.xpath(
            "//android.widget.EditText"
        ).get(timeout=3)
        if search_input:
            search_input.set_text(keyword)
            logger.debug(f"输入搜索关键词: {keyword}")
        else:
            logger.error("未找到搜索输入框")
            return False

        # 3. 点击搜索按钮
        d.xpath("//*[@text='搜索']").click(timeout=3)

        # 4. 等待结果并点击第 result_index 个
        import time
        time.sleep(1.5)  # 等待搜索结果加载

        results = d.xpath(
            "//*[@resource-id='cn.damai:id/result_item']"
        ).all()

        if not results:
            # 兜底：找可点击的演出卡片
            results = d.xpath(
                "//*[@class='android.widget.FrameLayout' and @clickable='true']"
            ).all()

        if results and len(results) > result_index:
            results[result_index].click()
            logger.info(f"搜索结果点击成功: 第 {result_index} 个")
            return True
        else:
            logger.warning(f"搜索结果不足: 找到 {len(results) if results else 0} 个")
            return False

    except Exception as e:
        logger.error(f"搜索演出失败: {e}")
        return False


def auto_navigate(
    d: u2.Device,
    item_url: str = "",
    keyword: str = "",
    city: str = "",
    date: str = "",
    timeout: float = 10.0,
) -> bool:
    """自动导航到目标演出

    优先级：item_url > keyword

    Args:
        d: uiautomator2 设备实例
        item_url: 商品链接
        keyword: 搜索关键词
        city: 目标城市
        date: 目标日期
        timeout: 超时秒数

    Returns:
        True 如果导航成功
    """
    logger.info(f"自动导航: url='{item_url}' keyword='{keyword}'")

    # 优先级 1: item_url
    if item_url:
        success = open_by_url(d, item_url)
        if success:
            return True

    # 优先级 2: keyword 搜索
    if keyword:
        success = search_by_keyword(d, keyword, timeout=timeout)
        if success:
            return True

    logger.error("自动导航失败: 请配置 item_url 或 keyword")
    return False
