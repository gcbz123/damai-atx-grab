import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

info = d.info
print(f"Activity: {info.get('currentActivity', '(empty)')}")
print(f"Display size: {info.get('displaySizeDpX', '')} x {info.get('displaySizeDpY', '')}")
print(f"Window size: {info.get('displayWidth', '')} x {info.get('displayHeight', '')}")

xml = d.dump_hierarchy()

# 提取所有 clickable 节点
print("\n=== 所有 clickable 节点 ===")
for m in re.finditer(r'<node([^>]*clickable="true"[^>]*)bounds="(\[[\d,]+\])"([^>]*)>', xml):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs)
    text_m = re.search(r'text="([^"]*)"', attrs)
    class_m = re.search(r'class="([^"]*)"', attrs)
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    rid_short = rid.replace('cn.damai:id/', '') if rid else ''
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        cx, cy = (x1+x2)//2, (y1+y2)//2
        print(f"  mid=({cx},{cy}) rid='{rid_short}' text='{text[:30]}' class={cls}")

# 提取所有包含 submit/order/pay/confirm 的节点
print("\n=== 提交/支付相关节点 ===")
for m in re.finditer(r'<node([^>]*)(?:resource-id="([^"]*(?:submit|order|pay|confirm|buy)[^"]*)"|text="([^"]*(?:提交|确认|购买|付款)[^"]*)"[^>]*)>', xml, re.IGNORECASE):
    full = m.group(0)
    rid_m = re.search(r'resource-id="([^"]*)"', full)
    text_m = re.search(r'text="([^"]*)"', full)
    bounds_m = re.search(r'bounds="(\[[\d,]+\])"', full)
    clickable_m = re.search(r'clickable="([^"]*)"', full)
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    bounds = bounds_m.group(1) if bounds_m else ""
    clickable = clickable_m.group(1) if clickable_m else ""
    rid_short = rid.replace('cn.damai:id/', '') if rid else ''
    text_short = text.strip()[:30] if text else ''
    print(f"  rid='{rid_short}' text='{text_short}' bounds={bounds} clickable={clickable}")

# 底部栏
print("\n=== 底部栏 ===")
for m in re.finditer(r'<node([^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])")[^>]*resource-id="cn\.damai:id/bottom_layout"[^>]*/?>', xml):
    print(f"  Found bottom_layout")

# 打印底部栏所有子节点
bottom_pattern = re.compile(r'<node[^>]*resource-id="cn\.damai\:id/bottom_layout"[^>]*>.*$', re.DOTALL)
bm = bottom_pattern.search(xml)
if bm:
    bottom_xml = bm.group(0)
    for m in re.finditer(r'<node([^>]*)/>', bottom_xml):
        attrs = m.group(1)
        rid_m = re.search(r'resource-id="([^"]*)"', attrs)
        text_m = re.search(r'text="([^"]*)"', attrs)
        bounds_m = re.search(r'bounds="(\[[\d,]+\])"', attrs)
        clickable_m = re.search(r'clickable="([^"]*)"', attrs)
        class_m = re.search(r'class="([^"]*)"', attrs)
        
        rid = rid_m.group(1) if rid_m else ""
        text = text_m.group(1) if text_m else ""
        bounds = bounds_m.group(1) if bounds_m else ""
        clickable = clickable_m.group(1) if clickable_m else ""
        cls = class_m.group(1) if class_m else ""
        
        rid_short = rid.replace('cn.damai:id/', '')
        text_short = text.strip()[:20] if text else ''
        coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds) if bounds else None
        mid = f'({(int(coords.group(1))+int(coords.group(3)))//2},{(int(coords.group(2))+int(coords.group(4)))//2})' if coords else ''
        print(f"  {rid_short:40s} text='{text_short}' bounds={bounds} mid={mid} clickable={clickable} class={cls}")
