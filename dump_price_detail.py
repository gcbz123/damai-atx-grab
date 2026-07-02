import uiautomator2 as u2
import xml.etree.ElementTree as ET
import re
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 提取 layout_price 区域
price_pattern = re.compile(r'<node[^>]*resource-id="cn\.damai\:id/layout_price"[^>]*>.*?</node>', re.DOTALL)
pm = price_pattern.search(xml)
if pm:
    with open(r"C:\Users\Administrator\AppData\Local\Temp\opencode\full_price.xml", "w", encoding="utf-8") as f:
        f.write(pm.group(0))
    print("Full layout_price XML:")
    print(pm.group(0)[:3000])

# 提取 project_detail_perform_price_flowlayout 区域
flow_pattern = re.compile(r'<node[^>]*resource-id="cn\.damai\:id/project_detail_perform_price_flowlayout"[^>]*>.*?</node>', re.DOTALL)
fm = flow_pattern.search(xml)
if fm:
    with open(r"C:\Users\Administrator\AppData\Local\Temp\opencode\full_flow.xml", "w", encoding="utf-8") as f:
        f.write(fm.group(0))
    print("\n\nFull project_detail_perform_price_flowlayout XML:")
    print(fm.group(0)[:3000])
