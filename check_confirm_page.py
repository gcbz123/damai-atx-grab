import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time

# 先截图看看当前什么页面
d.screenshot(r"C:\Users\Administrator\AppData\Local\Temp\opencode\screenshot.png")
print("Screenshot saved")

# 多次 dump 看页面变化
for i in range(3):
    time.sleep(1)
    xml = d.dump_hierarchy()
    
    # 提取所有 clickable 节点
    clickables = []
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
            clickables.append({
                'mid': f'({(x1+x2)//2},{(y1+y2)//2})',
                'rid': rid.replace('cn.damai:id/', ''),
                'text': text[:30],
                'class': cls,
                'bounds': bounds
            })
    
    print(f"\n--- Dump #{i+1} (t={i+1}s) ---")
    print(f"Clickable nodes: {len(clickables)}")
    for c in clickables:
        print(f"  {c['mid']:15s} rid={c['rid']:30s} text='{c['text']}' class={c['class']}")
