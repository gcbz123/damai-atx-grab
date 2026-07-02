"""配置加载模块单元测试"""

import json
import tempfile
from pathlib import Path
import pytest

from src.config_loader import (
    load_config,
    _strip_jsonc_comments,
    AppConfig,
)


class TestStripJsoncComments:
    """测试 JSONC 注释剥离"""

    def test_strip_single_line_comment(self):
        jsonc = '{"key": "value" // 这是注释\n}'
        result = _strip_jsonc_comments(jsonc)
        assert "//" not in result

    def test_strip_multi_line_comment(self):
        jsonc = '{"key": /* 注释 */ "value"}'
        result = _strip_jsonc_comments(jsonc)
        assert "/*" not in result
        assert "*/" not in result

    def test_preserve_string_with_slashes(self):
        jsonc = '{"url": "http://example.com"}'
        result = _strip_jsonc_comments(jsonc)
        assert "http://example.com" in result

    def test_mixed_comments(self):
        jsonc = """
        {
            // 设备配置
            "udid": "",
            /* 多行
               注释 */
            "app_package": "cn.damai"
        }
        """
        result = _strip_jsonc_comments(jsonc)
        parsed = json.loads(result)
        assert parsed["udid"] == ""
        assert parsed["app_package"] == "cn.damai"


class TestLoadConfig:
    """测试配置加载"""

    def test_load_valid_config(self):
        """加载有效配置"""
        config_data = {
            "udid": "abc123",
            "app_package": "cn.damai",
            "city": "深圳",
            "date": "12.06",
            "price": "内场1199元",
            "users": ["张三"],
            "start_at": "2026-07-01 20:00:00",
            "warmup_sec": 120,
            "sprint_interval_ms": 50,
            "sprint_max_retries": 60,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonc", delete=False, encoding="utf-8"
        ) as f:
            json.dump(config_data, f, ensure_ascii=False)
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.udid == "abc123"
            assert config.city == "深圳"
            assert config.date == "12.06"
            assert config.users == ["张三"]
            assert config.start_at == "2026-07-01 20:00:00"
            assert config.warmup_sec == 120
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_load_config_with_comments(self):
        """加载含注释的 JSONC 配置"""
        jsonc_content = """
        {
            // 设备配置
            "udid": "",
            "city": "北京",
            "date": "12.07",
            "users": ["李四"],
            "start_at": "2026-07-02 20:00:00",
            "warmup_sec": 60,
            "sprint_interval_ms": 50,
            "sprint_max_retries": 30
        }
        """.encode("utf-8").decode("utf-8")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonc", delete=False, encoding="utf-8"
        ) as f:
            f.write(jsonc_content)
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.city == "北京"
            assert config.date == "12.07"
            assert config.users == ["李四"]
            assert config.warmup_sec == 60
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_missing_required_field(self):
        """缺失必填字段应抛出异常"""
        config_data = {
            "city": "深圳",
            # 缺少 users, date, start_at
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonc", delete=False, encoding="utf-8"
        ) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="配置校验失败"):
                load_config(config_path)
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_file_not_found(self):
        """配置文件不存在应抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_config.jsonc")

    def test_invalid_json(self):
        """无效 JSON 应抛出 ValueError"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonc", delete=False, encoding="utf-8"
        ) as f:
            f.write("{invalid json content}")
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="JSON 解析失败"):
                load_config(config_path)
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_default_values(self):
        """未设置的字段应使用默认值"""
        config_data = {
            "city": "深圳",
            "date": "12.06",
            "users": ["王五"],
            "start_at": "2026-07-01 20:00:00",
            "sprint_interval_ms": 50,
            "sprint_max_retries": 30,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonc", delete=False, encoding="utf-8"
        ) as f:
            json.dump(config_data, f, ensure_ascii=False)
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.udid == ""  # 默认值
            assert config.app_package == "cn.damai"  # 默认值
            assert config.ntp_server == "ntp.aliyun.com"  # 默认值
            assert config.probe_only is True  # 默认值
        finally:
            Path(config_path).unlink(missing_ok=True)
