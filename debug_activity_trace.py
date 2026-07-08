"""临时调试脚本：监听 Activity 切换以验证 P0/P1 关键字匹配

跑法：确保手机已唤醒并打开大麦详情页，然后跑这个脚本，
它会先点 (841, 2250) 一次（模拟点击购票），然后 100ms 间隔轮询并打印 Activity。
"""
import time
import uiautomator2 as u2

d = u2.connect("AN2FVB1913005525")

def info():
    return d.info.get("currentActivity", "")

print(f"初始 Activity: {info()!r}")
print("点击 (841, 2250) 立即购票...")
d.click(841, 2250)

start = time.time()
last_act = ""
while time.time() - start < 3.0:
    act = info()
    if act != last_act:
        elapsed = (time.time() - start) * 1000
        print(f"  [{elapsed:6.0f}ms] Activity: {act!r}")
        last_act = act
    time.sleep(0.02)
print(f"最终 Activity: {info()!r}")
