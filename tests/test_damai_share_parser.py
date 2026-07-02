"""大麦分享链接解析器单元测试"""
from typing import Optional
import pytest
from src.damai_share_parser import (
    extract_item_id,
    _parse_city_from_text,
    _parse_date_from_show_time,
    _parse_price_info,
    _parse_static_data_div,
    parse_item_page,
    parse_shared_url,
    ParseError,
)


class TestExtractItemId:
    def test_mobile_url_with_item_id(self):
        assert extract_item_id(
            "https://m.damai.cn/damai/home/index.html?itemId=123456"
        ) == "123456"

    def test_detail_url_with_id(self):
        assert extract_item_id(
            "https://detail.damai.cn/item.htm?id=789012"
        ) == "789012"

    def test_url_with_multiple_params(self):
        assert extract_item_id(
            "https://m.damai.cn/damai/home/index.html?itemId=999&foo=bar&baz=123"
        ) == "999"

    def test_short_url_with_item_id(self):
        assert extract_item_id(
            "https://d.damai.cn/short?itemId=345"
        ) == "345"

    def test_no_match_returns_none(self):
        assert extract_item_id("https://example.com/no-match") is None

    def test_empty_string_returns_none(self):
        assert extract_item_id("") is None


class TestParseCityFromText:
    def test_major_cities(self):
        assert _parse_city_from_text("北京国家体育场") == "北京"
        assert _parse_city_from_text("上海梅赛德斯奔驰") == "上海"
        assert _parse_city_from_text("深圳湾体育中心") == "深圳"

    def test_foreign_city_returns_none(self):
        assert _parse_city_from_text("New York") is None
        assert _parse_city_from_text("东京ドーム") is None


class TestParseDateFromShowTime:
    def test_full_format_dot(self):
        assert _parse_date_from_show_time("2024.12.31 周一 19:30") == "12.31"

    def test_full_format_dash(self):
        assert _parse_date_from_show_time("2024-12-31 19:30") == "12.31"

    def test_full_format_chinese(self):
        assert _parse_date_from_show_time("2024年12月31日 19:30") == "12.31"

    def test_chinese_month_day(self):
        assert _parse_date_from_show_time("12月31日 19:30") == "12.31"

    def test_single_digit_month(self):
        assert _parse_date_from_show_time("2024.1.5 周六") == "01.05"

    def test_pending_returns_none(self):
        assert _parse_date_from_show_time("时间待定") is None
        assert _parse_date_from_show_time("待定") is None

    def test_empty_returns_none(self):
        assert _parse_date_from_show_time("") is None
        assert _parse_date_from_show_time(None) is None


class TestParsePriceInfo:
    def test_all_available(self):
        sku_list = [
            {"skuName": "内场VIP", "price": "1980", "stockStatusName": "可售"},
            {"skuName": "看台A", "price": "980", "stockStatusName": "可售"},
        ]
        info = _parse_price_info(sku_list)
        assert info["price_text"] == "内场VIP1980元"
        assert info["price_index"] == 0
        assert len(info["price_list"]) == 2

    def test_skip_soldout(self):
        sku_list = [
            {"skuName": "VIP", "price": "1980", "stockStatusName": "售罄"},
            {"skuName": "普通", "price": "980", "stockStatusName": "可售"},
        ]
        info = _parse_price_info(sku_list)
        assert info["price_index"] == 1

    def test_empty_list(self):
        info = _parse_price_info([])
        assert info["price_text"] == ""
        assert info["price_index"] == 0


class TestParseStaticDataDiv:
    def test_finds_div_content(self):
        html = """
        <html><body>
        <div id="staticDataDefault" style="display: none">
        {"venue":{"venueCityName":"上海市"},"itemBase":{"showTime":"2026.07.11 周六 19:00"}}
        </div>
        </body></html>
        """
        result = _parse_static_data_div(html)
        assert result is not None
        assert result["venue"]["venueCityName"] == "上海市"
        assert result["itemBase"]["showTime"] == "2026.07.11 周六 19:00"

    def test_no_div_returns_none(self):
        html = "<html><body>no data</body></html>"
        assert _parse_static_data_div(html) is None

    def test_empty_div_returns_none(self):
        html = '<html><body><div id="staticDataDefault"></div></body></html>'
        assert _parse_static_data_div(html) is None


class TestParseItemPage:
    def test_full_page_parsing(self):
        html = """
        <html>
        <head>
        <title>【上海】演唱会名称 - 大麦网</title>
        <meta name="description" content="上海某场馆，2026.07.11 周六 19:00">
        </head>
        <body>
        <div id="staticDataDefault" style="display: none">
        {"venue":{"venueCityName":"上海市"},"itemBase":{"showTime":"2026.07.11 周六 19:00"}}
        </div>
        </body>
        </html>
        """
        result = parse_item_page(html)
        assert result["city"] == "上海"
        assert result["date"] == "07.11"
        assert "演唱会名称" in result["name_from_title"]

    def test_minimal_page(self):
        html = "<html><head><title>演唱会 - 大麦网</title></head><body></body></html>"
        result = parse_item_page(html)
        assert result["name_from_title"] == "演唱会"

    def test_page_with_show_time_only(self):
        html = """
        <html><body>
        <div id="staticDataDefault" style="display: none">
        {"itemBase":{"showTime":"2026.08.15 周六 20:00"}}
        </div>
        </body></html>
        """
        result = parse_item_page(html)
        assert result["date"] == "08.15"
        assert result["show_time"] == "2026.08.15 周六 20:00"
