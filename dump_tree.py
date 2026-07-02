import uiautomator2 as u2
import xml.etree.ElementTree as ET
import re
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(3)

xml = d.dump_hierarchy()

# 写完整 XML
with open(r"C:\Users\Administrator\AppData\Local\Temp\opencode\full_dump.xml", "w", encoding="utf-8") as f:
    f.write(xml)

# 解析 XML
xml_clean = xml.replace('<?xml version="1.0" encoding="utf-8"?>', '')
xml_clean = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_clean)
root = ET.fromstring(xml_clean)

def walk(elem, depth=0, max_depth=12):
    """遍历节点树"""
    if depth > max_depth:
        return
    rid = elem.get('resource-id', '')
    text = elem.get('text', '')
    clickable = elem.get('clickable', '')
    bounds = elem.get('bounds', '')
    cls = elem.get('class', '')
    
    # 只打印大麦的节点
    if 'cn.damai' in (rid or '') or 'clickable=true' in (clickable or '') or text:
        indent = "  " * depth
        rid_short = rid.replace('cn.damai:id/', '') if rid else ''
        text_short = text.replace('\n', ' ').strip()[:40] if text else ''
        print(f"{indent}{rid_short:50s} text='{text_short}' clickable={clickable} bounds={bounds}")
    
    for child in elem:
        walk(child, depth + 1, max_depth)

walk(root)
