import uiautomator2 as u2
import re

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 提取 id_sku_main_content_layout 区域
main_pattern = re.compile(r'<node[^>]*resource-id="cn\.damai\:id/id_sku_main_content_layout"[^>]*>.*?</node>', re.DOTALL)
mm = main_pattern.search(xml)
if mm:
    with open(r"C:\Users\Administrator\AppData\Local\Temp\opencode\main_content.xml", "w", encoding="utf-8") as f:
        f.write(mm.group(0))
    print("Found id_sku_main_content_layout region")
    
    # 统计 clickable 节点
    clickable_count = len(re.findall(r'clickable="true"', mm.group(0)))
    print(f"Clickable nodes in main_content: {clickable_count}")
    
    # 提取所有 clickable 节点
    print("\n=== Main content clickable 节点 ===")
    for m in re.finditer(r'<node([^>]*clickable="true"[^>]*)bounds="(\[[\d,]+\])"([^>]*)>', mm.group(0)):
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
            cx, cy = (x1+x2)//2, (y1+y2)//2
            print(f"  bounds=({x1},{y1})-({x2},{y2}) mid=({cx},{cy}) rid={rid} text='{text}' class={cls}")
else:
    print("No id_sku_main_content_layout found")

# 全局 clickable 节点数量
global_clickable = len(re.findall(r'clickable="true"', xml))
print(f"\nTotal clickable nodes in page: {global_clickable}")

# 提取所有 clickable 节点
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
        cx, cy = (x1+x2)//2, (y1+y2)//2
        print(f"  bounds=({x1},{y1})-({x2},{y2}) mid=({cx},{cy}) rid={rid} text='{text}' class={cls}")
