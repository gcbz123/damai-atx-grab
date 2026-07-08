"""临时调试：测量 d.info vs d.app_current() 的开销"""
import time
import uiautomator2 as u2

d = u2.connect("AN2FVB1913005525")

# warm up
for _ in range(2):
    d.info
    d.app_current()

# d.info
t = time.time()
for _ in range(5):
    d.info
elapsed_info = (time.time() - t) * 1000
print(f"d.info 5次: {elapsed_info:.0f}ms, avg {elapsed_info/5:.0f}ms/次")

# d.app_current()
t = time.time()
for _ in range(5):
    d.app_current()
elapsed_ac = (time.time() - t) * 1000
print(f"d.app_current 5次: {elapsed_ac:.0f}ms, avg {elapsed_ac/5:.0f}ms/次")
