"""大麦分享链接信息抓取模块

解析大麦商品分享链接，自动提取演出信息（城市、日期、票价等）。
"""

import json
import re
import urllib.request
import urllib.error
from typing import Optional

from loguru import logger


def _parse_item_id(url: str) -> Optional[str]:
    """从大麦分享链接中提取商品 ID

    支持格式:
      - https://m.damai.cn/damai/home/index.html?itemId=XXX
      - https://detail.damai.cn/item.htm?id=XXX
      - https://detail.damai.com/item.htm?id=XXX
      - https://m.damai.cn/app_damai/... (itemId=XXX 或 id=XXX)

    Returns:
        itemId 字符串，提取失败返回 None
    """
    # 优先匹配 itemId 参数（大麦移动端格式）
    m = re.search(r'[?&]itemId=(\d+)', url)
    if m:
        return m.group(1)

    # 匹配 id 参数（PC 详情页格式）
    m = re.search(r'[?&]id=(\d+)', url)
    if m:
        return m.group(1)

    # 匹配 URL 路径中的数字 ID（某些短链接格式）
    m = re.search(r'/item/(\d+)', url)
    if m:
        return m.group(1)

    return None


def _build_detail_url(item_id: str) -> str:
    """根据 itemId 构建详情页 URL

    Args:
        item_id: 商品 ID

    Returns:
        移动端详情页 URL
    """
    return f"https://m.damai.cn/damai/home/index.html?itemId={item_id}"


def _fetch_page(url: str, timeout: int = 10) -> Optional[str]:
    """抓取页面 HTML

    Args:
        url: 目标 URL
        timeout: 超时秒数

    Returns:
        HTML 文本，失败返回 None
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.6099.230 Mobile Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            logger.debug(f"页面抓取成功: {len(html)} 字节")
            return html
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP 错误 {e.code}: {url}")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"网络错误: {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"抓取异常: {e}")
        return None


def _extract_json_from_script(html: str, var_name: str) -> Optional[dict]:
    """从 HTML 中的 <script> 标签提取 JSON 数据

    匹配形如: window.__INITIAL_STATE__ = {...} 或 window.__NUXT__ = {...} 等

    Args:
        html: 页面 HTML
        var_name: JavaScript 变量名（如 __INITIAL_STATE__）

    Returns:
        解析后的字典，失败返回 None
    """
    # 匹配 <script>...</script> 中包含 var_name = {...} 的块
    pattern = re.compile(
        rf'<script[^>]*>.*?{var_name}\s*=\s*(\{{.*?\}})\s*;?\s*</script>',
        re.DOTALL,
    )
    m = pattern.search(html)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_from_nuxt(html: str) -> Optional[dict]:
    """从 __NUXT__ JSON 中提取数据

    __NUXT__ 格式: window.__NUXT__ = { ... } 或直接 JSON 对象

    Args:
        html: 页面 HTML

    Returns:
        解析后的字典
    """
    # 尝试完整模式: window.__NUXT__ = (function(){... return {...}})()
    m = re.search(
        r'window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*</script>',
        html,
        re.DOTALL,
    )
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试短模式
    # __NUXT__ 数据通常有嵌套对象
    data = _extract_json_from_script(html, "__NUXT__")
    if data:
        return data
    return None


def _extract_item_info_from_state(state: dict) -> Optional[dict]:
    """从页面状态数据中提取演出信息

    遍历常见的数据路径，找到 itemInfo 或演出详情

    Args:
        state: 页面状态 JSON

    Returns:
        提取到的演出信息字典，失败返回 None
    """
    # 深搜常见的 data 路径
    paths = [
        ["itemInfo"],
        ["detail", "itemInfo"],
        ["itemDetail", "itemInfo"],
        ["store", "itemInfo"],
        ["data", "itemInfo"],
        ["detail", "data", "item"],
        ["data", "item"],
        ["item"],
    ]

    for path in paths:
        obj = state
        try:
            for key in path:
                obj = obj[key]
            if isinstance(obj, dict) and ("cityName" in obj or "itemName" in obj or "showName" in obj):
                return obj
        except (KeyError, TypeError):
            continue

    return None


def _extract_by_regex(html: str) -> dict:
    """通过正则从 HTML 中提取基本信息（兜底方案）

    Args:
        html: 页面 HTML

    Returns:
        提取到的信息字典（可能为空）
    """
    info = {}

    # 提取标题
    m = re.search(r'<title>(.*?)</title>', html)
    if m:
        title = m.group(1).strip()
        # 去除常见的后缀
        title = re.sub(r'\s*[-|·]\s*大麦.*$', '', title)
        info["title"] = title

    # 提取城市（在页面中搜索常见模式）
    city_patterns = [
        r'城市[：:]\s*([^\s<]{2,4})',
        r'"cityName"\s*[：:]\s*"([^"]+)"',
        r'cityName["\']?\s*:\s*["\']([^"\']+)["\']',
    ]
    for pat in city_patterns:
        m = re.search(pat, html)
        if m:
            info["city"] = m.group(1)
            break

    # 提取日期
    date_patterns = [
        r'"showTime"\s*:\s*"(\d{4}[-/]\d{2}[-/]\d{2})"',
        r'"showTime"\s*:\s*"(\d{2}\.\d{2})"',
        r'演出时间[：:]\s*([^\s<]{4,20})',
        r'\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}',
    ]
    for pat in date_patterns:
        m = re.search(pat, html)
        if m:
            info["date"] = m.group(0) if "演出时间" in pat else m.group(1)
            # 从完整日期中提取 MM.DD 格式
            date_match = re.search(r'(\d{2})[-/](\d{2})', info["date"])
            if date_match:
                info["date"] = f"{date_match.group(1)}.{date_match.group(2)}"
            break

    # 提取票价信息
    price_patterns = [
        r'"priceList"\s*:\s*\[(.*?)\]',
        r'"price"\s*:\s*"(\d+)"',
        r'票价[：:]\s*([^<]{2,50})',
    ]
    for pat in price_patterns:
        m = re.search(pat, html)
        if m:
            info["price_raw"] = m.group(1)
            break

    # 提取表演名称
    m = re.search(r'"itemName"\s*:\s*"([^"]+)"', html)
    if m:
        info["item_name"] = m.group(1)

    m = re.search(r'"showName"\s*:\s*"([^"]+)"', html)
    if m:
        info["item_name"] = m.group(1)

    return info


def _extract_structured(html: str) -> dict:
    """从页面中提取结构化的演出信息

    优先级:
      1. __NUXT__ 数据
      2. __INITIAL_STATE__ 数据
      3. 正则兜底

    Args:
        html: 页面 HTML

    Returns:
        信息字典
    """
    # 策略 1: 尝试 __NUXT__
    nuxt = _extract_json_from_nuxt(html)
    if nuxt:
        item = _extract_item_info_from_state(nuxt)
        if item:
            logger.info("从 __NUXT__ 提取到演出信息")
            return _normalize_item_info(item)

    # 策略 2: 尝试 __INITIAL_STATE__
    init_state = _extract_json_from_script(html, "__INITIAL_STATE__")
    if init_state:
        item = _extract_item_info_from_state(init_state)
        if item:
            logger.info("从 __INITIAL_STATE__ 提取到演出信息")
            return _normalize_item_info(item)

    # 策略 3: 尝试 __NEXT_DATA__
    next_data = _extract_json_from_script(html, "__NEXT_DATA__")
    if next_data:
        item = _extract_item_info_from_state(next_data)
        if item:
            logger.info("从 __NEXT_DATA__ 提取到演出信息")
            return _normalize_item_info(item)

    # 兜底: 正则提取
    info = _extract_by_regex(html)
    if info:
        logger.info("通过正则提取到部分演出信息")
    return info


def _normalize_item_info(item: dict) -> dict:
    """将原始 itemInfo 转换为统一格式

    Args:
        item: 原始物品信息字典

    Returns:
        标准化的信息字典
    """
    info = {}

    # 演出名称
    info["title"] = item.get("itemName") or item.get("showName") or item.get("name", "")

    # 城市
    city = (
        item.get("cityName")
        or item.get("city")
        or item.get("venueCity")
        or ""
    )
    # 去掉"市"后缀
    city = re.sub(r'市$', '', city)
    info["city"] = city

    # 日期 — 取首个演出日期
    show_time = item.get("showTime") or item.get("performanceTime") or ""
    if isinstance(show_time, list):
        show_time = show_time[0] if show_time else ""
    if show_time:
        m = re.search(r'(\d{2})[-/.](\d{2})', show_time)
        if m:
            info["date"] = f"{m.group(1)}.{m.group(2)}"
        else:
            info["date"] = show_time[:10] if len(show_time) >= 10 else show_time

    # 票价
    price_list = item.get("priceList") or item.get("priceRange") or []
    price_str = ""
    if isinstance(price_list, list) and price_list:
        prices = []
        for p in price_list[:2]:  # 最多取前两种票价
            if isinstance(p, dict):
                name = p.get("name") or p.get("priceName", "")
                val = p.get("price") or p.get("priceValue", "")
                if name and val:
                    prices.append(f"{name}{val}元")
                elif val:
                    prices.append(f"{val}元")
            elif isinstance(p, str):
                prices.append(p)
        if prices:
            price_str = " / ".join(prices)
    elif isinstance(price_list, str):
        price_str = price_list

    if price_str:
        info["price"] = price_str

    # 原价取最低值用于 price_index
    if isinstance(price_list, list) and price_list:
        min_price = None
        for i, p in enumerate(price_list):
            if isinstance(p, dict):
                val = p.get("price") or p.get("priceValue", "0")
                try:
                    pv = int(val)
                    if min_price is None or pv < min_price:
                        min_price = pv
                        info["price_index"] = i
                except (ValueError, TypeError):
                    pass

    # itemId
    info["item_id"] = item.get("itemId") or item.get("id", "")

    # venue
    info["venue"] = item.get("venueName") or item.get("venue", "")

    return info


class DamaiFetcher:
    """大麦演出信息抓取器

    通过分享链接自动获取演出详情并填充配置。
    """

    def __init__(self, timeout: int = 10):
        """
        Args:
            timeout: HTTP 请求超时秒数
        """
        self.timeout = timeout

    def fetch(self, url: str) -> Optional[dict]:
        """抓取演出信息

        Args:
            url: 大麦商品分享链接

        Returns:
            包含以下字段的字典，失败返回 None:
                - title: 演出名称
                - city: 城市
                - date: 日期 (MM.DD 格式)
                - price: 票价描述
                - price_index: 票价索引
                - item_id: 商品 ID

            示例:
                {
                    "title": "刘若英 [飞行日] 巡回演唱会-深圳站",
                    "city": "深圳",
                    "date": "12.06",
                    "price": "看台499元 / 看台699元",
                    "price_index": 0,
                    "item_id": "1234567890",
                }
        """
        # 1. 提取 itemId
        item_id = _parse_item_id(url)
        if not item_id:
            logger.error(f"无法从链接中提取商品 ID: {url}")
            return None

        logger.info(f"提取到商品 ID: {item_id}")

        # 2. 抓取页面
        detail_url = _build_detail_url(item_id)
        html = _fetch_page(detail_url, timeout=self.timeout)
        if not html:
            logger.error(f"抓取页面失败: {detail_url}")
            return None

        # 3. 提取信息
        info = _extract_structured(html)
        info["item_id"] = item_id

        # 4. 如果没提取到 item_url，补上
        if "item_url" not in info or not info.get("item_url"):
            info["item_url"] = detail_url

        if info.get("city") or info.get("date") or info.get("price"):
            logger.info(f"成功提取演出信息: {info.get('title', '')} {info.get('city', '')} {info.get('date', '')}")
            return info

        logger.warning("未能从页面中提取到演出信息")
        return None
