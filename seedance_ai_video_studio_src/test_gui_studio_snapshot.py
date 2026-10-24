"""
Snapshot tester for the updated PyQt6 GUI with Aspect Studio Canvas.
"""
import sys, os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from main_gui_pyqt import SeedanceMainWindow

def snapshot():
    app = QApplication.instance() or QApplication(sys.argv)
    win = SeedanceMainWindow()
    win.resize(1380, 880)
    win.show()

    # Switch to Create Video Tab (index 1)
    win.nav_list.setCurrentRow(1)

    def grab():
        pix = win.grab()
        out_path = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\gui_aspect_studio_preview.png"
        pix.save(out_path, "PNG")
        print(f"✅ Saved GUI snapshot to: {out_path}")
        win.close()
        app.quit()

    QTimer.singleShot(1500, grab)
    app.exec()

if __name__ == '__main__':
    snapshot()
