import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

# 先 dump 原始页面
xml1 = d.dump_hierarchy()
print("=== 原始页面 clickable ===")
for m in re.finditer(r'<node\b([^>]*clickable="true"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', xml1, re.IGNORECASE):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    text_m = re.search(r'text="([^"]*)"', attrs, re.IGNORECASE)
    class_m = re.search(r'class="([^"]*)"', attrs, re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        cx, cy = (x1+x2)//2, (y1+y2)//2
        rid_short = rid.replace('cn.damai:id/', '')
        print(f"  mid=({cx},{cy}) rid='{rid_short}' text='{text}' class={cls}")

# 打印票档区域所有 FrameLayout
print("\n=== 票档区域内所有 FrameLayout ===")
for m in re.finditer(r'<node\b([^>]*class="android\.widget\.FrameLayout"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', xml1, re.IGNORECASE):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    clickable_m = re.search(r'clickable="([^"]*)"', attrs, re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    clickable = clickable_m.group(1) if clickable_m else ""
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        cx, cy = (x1+x2)//2, (y1+y2)//2
        rid_short = rid.replace('cn.damai:id/', '')
        print(f"  mid=({cx},{cy}) rid='{rid_short}' clickable={clickable}")

# 方案: 长按票档区域试试
print("\n=== 尝试长按 (236, 1066) ===")
d.long_click(236, 1066, 0.5)
time.sleep(1)

xml2 = d.dump_hierarchy()
print("\n=== 长按后 clickable ===")
for m in re.finditer(r'<node\b([^>]*clickable="true"[^>]*)bounds="(\[\d+,\d+\]\[\d+,\d+\])"([^>]*)>', xml2, re.IGNORECASE):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs, re.IGNORECASE)
    text_m = re.search(r'text="([^"]*)"', attrs, re.IGNORECASE)
    class_m = re.search(r'class="([^"]*)"', attrs, re.IGNORECASE)
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        cx, cy = (x1+x2)//2, (y1+y2)//2
        rid_short = rid.replace('cn.damai:id/', '')
        print(f"  mid=({cx},{cy}) rid='{rid_short}' text='{text}' class={cls}")

# 检查 btn_buy_view 状态
buy_m = re.search(r'resource-id="cn\.damai\:id/btn_buy_view"[^>]*clickable="([^"]*)"[^>]*bounds="(\[\d+,\d+\]\[\d+,\d+\])"', xml2, re.IGNORECASE)
if buy_m:
    print(f"\nbtn_buy_view: clickable={buy_m.group(1)} bounds={buy_m.group(2)}")
else:
    print("\nbtn_buy_view: NOT FOUND")

# 检查是否有数量按钮
jian_m = re.search(r'resource-id="cn\.damai\:id/img_jian"', xml2, re.IGNORECASE)
jia_m = re.search(r'resource-id="cn\.damai\:id/img_jia"', xml2, re.IGNORECASE)
print(f"img_jian: {'FOUND' if jian_m else 'NOT FOUND'}")
print(f"img_jia: {'FOUND' if jia_m else 'NOT FOUND'}")
