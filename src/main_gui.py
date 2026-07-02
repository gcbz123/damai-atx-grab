"""GUI 模式入口

启动 PyQt6 图形界面对抢票流程进行可视化配置和控制。

用法:
    python -m src.main_gui
"""

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.app import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
