import uiautomator2 as u2
import xml.etree.ElementTree as ET
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 清理
xml_clean = xml.replace('<?xml version="1.0" encoding="utf-8"?>', '')
xml_clean = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_clean)

root = ET.fromstring(xml_clean)

def walk(elem, depth=0, max_depth=8):
    if depth > max_depth:
        return
    rid = elem.get('resource-id', '')
    if 'cn.damai' not in rid and depth > 1:
        return
    
    text = (elem.get('text') or '').replace('\n', ' ').strip()[:30]
    clickable = elem.get('clickable', '')
    bounds = elem.get('bounds', '')
    cls = elem.get('class', '').split('.')[-1]
    
    indent = "  " * depth
    rid_short = rid.replace('cn.damai:id/', '')
    
    if rid_short or clickable == 'true' or text:
        print(f"{indent}{rid_short:40s} text='{text}' clickable={clickable} bounds={bounds}")
    
    for child in elem:
        walk(child, depth + 1, max_depth)

walk(root)
