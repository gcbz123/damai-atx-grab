import uiautomator2 as u2
import re

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 提取 layout_price 区域（票档选择区）
price_pattern = re.compile(r'<node[^>]*resource-id="cn\.damai\:id/layout_price"[^>]*>.*?</node>', re.DOTALL)
pm = price_pattern.search(xml)
if pm:
    with open(r"C:\Users\Administrator\AppData\Local\Temp\opencode\price_region.xml", "w", encoding="utf-8") as f:
        f.write(pm.group(0))
    print("Found layout_price region")
else:
    print("No layout_price found")

# 提取 sku_contanier 区域
sku_pattern = re.compile(r'<node[^>]*resource-id="cn\.damai\:id/sku_contanier"[^>]*>.*?</node>', re.DOTALL)
sm = sku_pattern.search(xml)
if sm:
    with open(r"C:\Users\Administrator\AppData\Local\Temp\opencode\sku_region.xml", "w", encoding="utf-8") as f:
        f.write(sm.group(0))
    print("Found sku_contanier region")
else:
    print("No sku_contanier found")

# 提取所有 clickable 节点（全局）
print("\n=== 全局所有 clickable 节点 ===")
for m in re.finditer(r'<node([^>]*clickable="true"[^>]*)bounds="(\[[\d,]+\])"([^>]*)>', xml):
    attrs = m.group(1) + m.group(3)
    bounds = m.group(2)
    rid_m = re.search(r'resource-id="([^"]*)"', attrs)
    text_m = re.search(r'text="([^"]*)"', attrs)
    class_m = re.search(r'class="([^"]*)"', attrs)
    rid = rid_m.group(1) if rid_m else ""
    text = text_m.group(1) if text_m else ""
    cls = class_m.group(1) if class_m else ""
    coords = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if coords:
        x1, y1, x2, y2 = int(coords.group(1)), int(coords.group(2)), int(coords.group(3)), int(coords.group(4))
        print(f"  bounds=({x1},{y1})-({x2},{y2}) rid={rid} text='{text}' class={cls}")
