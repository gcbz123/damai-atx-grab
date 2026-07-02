import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import uiautomator2 as u2
import xml.etree.ElementTree as ET
import re

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 清理 XML 命名空间
xml_clean = xml.replace('<?xml version="1.0" encoding="utf-8"?>', '')
xml_clean = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_clean)

try:
    root = ET.fromstring(xml_clean)
except ET.ParseError as e:
    print(f"XML parse error: {e}")
    print("First 500 chars:", xml_clean[:500])
    exit(1)

def find_clickable(elem, depth=0):
    clickable = []
    if elem.get('clickable') == 'true':
        coords = elem.get('bounds')
        if coords:
            import re as re2
            m = re2.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', coords)
            if m:
                x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                cx, cy = (x1+x2)//2, (y1+y2)//2
                clickable.append({
                    'rid': elem.get('resource-id', ''),
                    'text': elem.get('text', ''),
                    'class': elem.get('class', ''),
                    'bounds': coords,
                    'mid': f'({cx},{cy})'
                })
    for child in elem:
        clickable.extend(find_clickable(child, depth+1))
    return clickable

clickables = find_clickable(root)
print(f"Total clickable nodes: {len(clickables)}")
print("\n=== 所有 clickable 节点 ===")
for c in clickables:
    print(f"  bounds={c['bounds']} mid={c['mid']} rid={c['rid']} text='{c['text']}' class={c['class']}")

# 特别关注 btn_buy_view
print("\n=== btn_buy_view 详细信息 ===")
for elem in root.iter():
    rid = elem.get('resource-id', '')
    if 'btn_buy_view' in rid:
        print(f"  resource-id: {rid}")
        print(f"  bounds: {elem.get('bounds')}")
        print(f"  clickable: {elem.get('clickable')}")
        print(f"  class: {elem.get('class')}")
        print(f"  text: {elem.get('text')}")
        print(f"  content-desc: {elem.get('content-desc')}")
        print(f"  enabled: {elem.get('enabled')}")

# 也关注所有包含 price 的节点
print("\n=== 所有 price 相关节点 ===")
for elem in root.iter():
    rid = elem.get('resource-id', '')
    text = elem.get('text', '')
    if 'price' in rid.lower() or 'price' in text.lower() or 'sku' in rid.lower():
        bounds = elem.get('bounds', '')
        clickable = elem.get('clickable', '')
        print(f"  rid={rid}, text='{text}', bounds={bounds}, clickable={clickable}")
