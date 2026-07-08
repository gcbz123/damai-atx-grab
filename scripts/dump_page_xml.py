"""导出当前设备页面的 XML 结构到文件（调试用）"""
import sys, os
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config_loader import load_config
import uiautomator2 as u2


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config.jsonc")
    cfg = load_config(config_path)
    udid = cfg.udid or None
    d = u2.connect(udid)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outpath = os.path.join(script_dir, f"page_dump_{ts}.xml")

    xml = d.dump_hierarchy()
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"页面 XML 已保存到: {outpath}")
    print(f"文件大小: {len(xml)} 字节")

    # 检查关键文本
    if "\u7acb\u5373\u63d0\u4ea4" in xml:
        print("[OK] XML 中包含「立即提交」")
    else:
        print("[!!] XML 中不包含「立即提交」")

    submit_count = xml.lower().count("submit")
    print(f"[OK] XML 中包含 {submit_count} 处 submit（不区分大小写）")


if __name__ == "__main__":
    main()
