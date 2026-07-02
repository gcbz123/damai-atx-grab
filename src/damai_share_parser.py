"""大麦分享链接解析器

解析大麦 App 分享链接，从详情页 HTML 中提取演出信息，
用于 GUI 自动填充配置字段。

用法:
    parser = DamaiShareParser()
    result = parser.parse("https://m.damai.cn/...?itemId=1234567890")
    # result = {"name": "..., "city": "...", "date": "...", ...}
"""

import json
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger


# 大麦分享链接中提取 itemId 的正则模式
_URL_PATTERNS = [
    re.compile(r"[?&]itemId[=:](\d+)"),
    re.compile(r"[?&]id[=:](\d+)"),
    re.compile(r"detail\.damai\.cn.*[?&]id[=:](\d+)"),
    re.compile(r"/item/(\d+)"),
    re.compile(r"itemId=(\d+)"),
]

_DETAIL_URL = "https://detail.damai.cn/item.htm?id={}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.damai.cn/",
}


class ParseError(Exception):
    """解析失败"""
    pass


def extract_item_id(url: str) -> Optional[str]:
    """从分享链接中提取商品 ID

    Args:
        url: 大麦分享链接（各种格式）

    Returns:
        商品 ID 字符串，或 None
    """
    for pattern in _URL_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None


def _parse_city_from_text(text: str) -> Optional[str]:
    """从文本中提取城市名"""
    # 常见城市列表（覆盖主要城市）
    cities = [
        "北京", "上海", "广州", "深圳", "天津", "重庆",
        "杭州", "南京", "苏州", "成都", "武汉", "西安",
        "长沙", "郑州", "青岛", "大连", "宁波", "厦门",
        "福州", "合肥", "昆明", "贵阳", "南宁", "海口",
        "兰州", "西宁", "银川", "乌鲁木齐", "呼和浩特",
        "拉萨", "哈尔滨", "长春", "沈阳", "石家庄",
        "太原", "济南", "南昌",
    ]
    for city in cities:
        if city in text:
            return city
    return None


def _parse_date_from_show_time(show_time: str) -> Optional[str]:
    """从演出时间文本中提取日期

    处理格式:
        "2024.12.31 周一 19:30"  → "12.31"
        "2024-12-31"             → "12.31"
        "2024年12月31日"          → "12.31"
        "12月31日"               → "12.31"
        "时间待定"               → None
    """
    if not show_time:
        return None
    show_time = show_time.strip()
    # 跳过待定
    if "待定" in show_time or "TBD" in show_time.upper():
        return None

    # 匹配 yyyy.MM.dd / yyyy-MM-dd / yyyy年MM月dd日
    m = re.search(r"(\d{4})[/.年-](\d{1,2})[/.月-](\d{1,2})", show_time)
    if m:
        month = m.group(2).zfill(2)
        day = m.group(3).zfill(2)
        return f"{month}.{day}"

    # 匹配 MM月dd日
    m = re.search(r"(\d{1,2})月(\d{1,2})日", show_time)
    if m:
        return f"{m.group(1).zfill(2)}.{m.group(2).zfill(2)}"

    # 匹配 MM.dd
    m = re.search(r"(\d{2})\.(\d{2})", show_time)
    if m:
        return f"{m.group(1)}.{m.group(2)}"

    return None


def _parse_price_info(sku_list: list) -> dict:
    """从票价列表提取价格信息

    Args:
        sku_list: 票价列表，每个元素含 price, skuName, stockStatusName

    Returns:
        {"price_text": "内场1199元", "price_index": 0, "price_list": [...]}
    """
    if not sku_list:
        return {"price_text": "", "price_index": 0}

    # 构建票价描述
    prices = []
    for sku in sku_list:
        name = sku.get("skuName", "")
        price = sku.get("price", "")
        status = sku.get("stockStatusName", "")
        if name and price:
            prices.append({
                "name": name,
                "price": price,
                "status": status,
            })

    if not prices:
        return {"price_text": "", "price_index": 0}

    # 取第一个在售票价作为默认
    default_idx = 0
    for i, p in enumerate(prices):
        if p.get("status") != "售罄":
            default_idx = i
            break

    default = prices[default_idx]
    price_text = f"{default['name']}{default['price']}元"

    return {
        "price_text": price_text,
        "price_index": default_idx,
        "price_list": prices,
    }


def _parse_static_data_div(html: str) -> Optional[dict]:
    """从 HTML 中提取 #staticDataDefault 内的 JSON 数据

    大麦详情页将演出数据放在一个隐藏的 div 中:
        <div id="staticDataDefault" style="display: none">{"venue":{...},"itemBase":{...}}</div>

    Args:
        html: 页面 HTML

    Returns:
        解析后的 JSON 字典，或 None
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div", id="staticDataDefault")
        if div:
            text = div.get_text(strip=True)
            if text:
                return json.loads(text)
    except Exception:
        pass

    # fallback: regex
    m = re.search(
        r'<div\s+id="staticDataDefault"[^>]*>([\s\S]*?)</div>',
        html, re.I
    )
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    return None


def parse_item_page(html: str) -> dict:
    """解析大麦详情页 HTML，提取演出信息

    Args:
        html: 页面 HTML

    Returns:
        包含演出信息的字典，可能的键:
            name: 演出名称
            city: 城市
            date: 日期 (MM.dd)
            venue: 场馆
            price_text: 票价描述
            price_index: 默认票价索引
    """
    result = {}

    # 1. 尝试从 #staticDataDefault 提取结构化数据
    state = _parse_static_data_div(html)
    if state:
        # itemBase 基本信息
        item_base = state.get("itemBase", {})
        if item_base.get("name"):
            result["name"] = item_base["name"]
        if item_base.get("showTime"):
            result["show_time"] = item_base["showTime"]

        # 场馆信息
        venue = state.get("venue", {})
        if venue.get("venueCityName"):
            result["city"] = venue["venueCityName"].replace("市", "")
        elif venue.get("venueProvinceName"):
            result["city"] = venue["venueProvinceName"].replace("省", "")

    # 2. 从 <title> 标签提取
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if title_match:
        title = title_match.group(1).strip()
        # 大麦标题格式: "【城市】演出名称 - 大麦网"
        # 或: "演出名称【网上订票】- 大麦网"
        title_clean = re.sub(r"\s*[-–—]\s*大麦网.*$", "", title).strip()
        title_clean = re.sub(r"【网上订票】", "", title_clean).strip()
        # 尝试提取 【城市】
        city_in_title = re.search(r"【(.+?)】", title_clean)
        if city_in_title:
            extracted_city = city_in_title.group(1)
            # 验证是否是城市名
            if _parse_city_from_text(extracted_city):
                result["city_from_title"] = extracted_city
        if "name" not in result:
            result["name_from_title"] = title_clean

    # 3. 从 meta description 提取
    desc_match = re.search(
        r'<meta\s+[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
        html, re.I
    )
    if desc_match:
        desc = desc_match.group(1)
        # description 通常包含城市、时间等信息
        if "city" not in result:
            city_from_desc = _parse_city_from_text(desc)
            if city_from_desc:
                result["city"] = city_from_desc
        if "show_time" not in result:
            date_from_desc = _parse_date_from_show_time(desc)
            if date_from_desc:
                result["date"] = date_from_desc

    # 4. 从 show_time 推导 date
    if "date" not in result and "show_time" in result:
        parsed_date = _parse_date_from_show_time(result["show_time"])
        if parsed_date:
            result["date"] = parsed_date

    # 5. 如果 city 从 venue 来但带"市"，去掉
    if "city" in result:
        result["city"] = result["city"].replace("市", "").replace("省", "")

    return result


def parse_shared_url(url: str, timeout: int = 10) -> dict:
    """解析大麦分享链接

    主入口函数。提取 item ID → 获取详情页 → 解析页面信息。

    Args:
        url: 大麦分享链接
        timeout: HTTP 请求超时（秒）

    Returns:
        配置字段字典（可直接用于填充 ConfigPanel），
        如果完全解析失败则抛出 ParseError。

    Raises:
        ParseError: 无法从链接中提取 item ID
    """
    item_id = extract_item_id(url)
    if not item_id:
        raise ParseError(f"无法从链接中提取商品 ID: {url}")

    logger.info(f"解析大麦分享链接, itemId={item_id}")

    detail_url = _DETAIL_URL.format(item_id)

    try:
        resp = requests.get(detail_url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        # 确保编码正确
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
    except requests.RequestException as e:
        raise ParseError(f"获取详情页失败: {e}")

    if not html:
        raise ParseError("获取的详情页为空")

    info = parse_item_page(html)

    # 组装最终结果
    result = {
        "item_url": detail_url,
        "item_id": item_id,
    }

    # 演出名称 → keyword（用于搜索）
    name = info.get("name") or info.get("name_from_title") or ""
    if name:
        # 去掉 【城市】 前缀
        clean_name = re.sub(r"^【.+?】", "", name).strip()
        result["keyword"] = clean_name

    # 城市
    city = (
        info.get("city")
        or info.get("city_from_title")
        or ""
    )
    if city:
        result["city"] = city

    # 日期
    if info.get("date"):
        result["date"] = info["date"]

    # 票价
    if info.get("price_text"):
        result["price"] = info["price_text"]
    if "price_index" in info:
        result["price_index"] = info["price_index"]

    logger.info(f"解析完成: city={result.get('city')}, "
                f"date={result.get('date')}, "
                f"keyword={result.get('keyword')}")

    return result
