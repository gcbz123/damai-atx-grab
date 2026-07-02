import uiautomator2 as u2
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = u2.connect()
import time
time.sleep(2)

xml = d.dump_hierarchy()

# 找到 bottom_layout 起始
bm = re.search(r'<node\b[^>]*resource-id="cn\.damai\:id/bottom_layout"', xml, re.IGNORECASE)
if bm:
    start = bm.start()
    chunk = xml[start:]
    # 找闭合标签 — 底部栏是最后一个大节点
    # 数括号
    depth = 0
    end = start
    in_tag = False
    for i, ch in enumerate(chunk):
        if ch == '<' and not chunk[max(0,i-1):i].endswith('\\'):
            in_tag = True
        if in_tag:
            if ch == '>':
                if chunk[max(0,i-1):i+1].startswith('</'):
                    depth -= 1
                    if depth < 0:
                        end = start + i + 1
                        break
                depth += 1
                in_tag = False
    
    bottom_xml = chunk[:end-start]
    print(bottom_xml[:5000])
