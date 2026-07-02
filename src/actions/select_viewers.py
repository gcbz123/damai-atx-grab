"""观演人勾选操作模块

添加观演人：
  1. 进入观演人选择页
  2. 根据配置的观演人列表勾选
  3. 点击确定返回
"""

from loguru import logger
import uiautomator2 as u2


def select_viewers(d: u2.Device, users: list[str], timeout: float = 5.0) -> bool:
    """勾选观演人

    Args:
        d: uiautomator2 设备实例
        users: 观演人姓名列表
        timeout: 超时秒数

    Returns:
        True 如果全部观演人勾选成功
    """
    if not users:
        logger.warning("观演人列表为空，跳过勾选")
        return False

    logger.info(f"开始勾选观演人: {users}")
    success = True

    for name in users:
        try:
            # 查找姓名对应的 CheckBox
            cb = d.xpath(
                f'//*[@text="{name}"]/../*[@class="android.widget.CheckBox"]'
            ).get(timeout=timeout)

            if cb is None:
                # 兜底：找同级 CheckBox
                cb = d.xpath(
                    f'//*[@text="{name}"]/following-sibling::*[@class="android.widget.CheckBox"]'
                ).get(timeout=2)

            if cb is None:
                # 再兜底：找整行可点击区域
                cb = d.xpath(f'//*[@text="{name}"]').get(timeout=2)

            if cb:
                cb.click()
                logger.info(f"观演人已勾选: {name}")
            else:
                logger.warning(f"未找到观演人: {name}")
                success = False
        except Exception as e:
            logger.warning(f"勾选观演人失败 {name}: {e}")
            success = False

    # 点击确定按钮
    try:
        d.xpath("//*[@text='确定']").click(timeout=3)
        logger.debug("点击确定按钮")
    except Exception:
        pass

    return success
