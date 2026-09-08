APP_STYLESHEET = r"""
QMainWindow {
    background: #15181b;
    color: #e8ecef;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 12px;
}

QWidget {
    color: #e8ecef;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 12px;
}

QWidget#AppRoot {
    background: #15181b;
}

QFrame#TopBar {
    background: #202428;
    border: none;
    border-bottom: 1px solid #394148;
}

QLabel#BrandTitle {
    background: transparent;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #f2f5f6;
}

QLabel#BrandSubtitle {
    background: transparent;
    font-size: 7px;
    color: #aeb7be;
}

QPushButton#StageButton {
    background: #30363b;
    color: #e9eef0;
    border: 1px solid #4b555d;
    border-radius: 6px;
    min-width: 138px;
    min-height: 40px;
    padding: 0 18px;
    font-size: 16px;
    font-weight: 700;
}

QPushButton#StageButton:hover {
    background: #3b444a;
    border-color: #5f6d76;
}

QPushButton#StageButton:checked {
    background: #197987;
    border: 2px solid #67d5df;
    color: white;
}

QFrame#LeftSidebar, QFrame#RightSidebar {
    background: #202428;
    border: none;
}

QFrame#LeftSidebar QLabel, QFrame#RightSidebar QLabel,
QFrame#LeftSidebar QRadioButton, QFrame#RightSidebar QRadioButton {
    background: transparent;
}

QPushButton#PrimaryAction {
    background: #197987;
    color: white;
    border: 1px solid #56c9d5;
    border-radius: 7px;
    min-height: 44px;
    padding: 0 12px;
    font-size: 15px;
    font-weight: 800;
}

QPushButton#PrimaryAction:hover {
    background: #208c9b;
    border-color: #7adbe3;
}

QPushButton#PrimaryAction:pressed {
    background: #126875;
}

QLabel#SectionTitle {
    color: #f0f3f4;
    font-weight: 800;
    font-size: 15px;
}

QFrame#SectionLine {
    background: #4b555d;
    max-height: 1px;
    min-height: 1px;
}

QLabel#SidebarText {
    color: #e2e7ea;
    font-size: 14px;
}

QLabel#StatusOk {
    color: #65d78a;
    font-weight: 700;
    font-size: 14px;
}

QLabel#StatusWarn {
    color: #e6bd62;
    font-weight: 700;
    font-size: 14px;
}

QLabel#StatusError {
    color: #ef7770;
    font-weight: 700;
    font-size: 14px;
}

QLabel#StatusWaiting {
    color: #aeb8bf;
    font-weight: 700;
    font-size: 14px;
}

QLabel#StatusMuted {
    background: transparent;
    color: #98a3aa;
}

QComboBox {
    background: #2a2f33;
    color: #edf1f2;
    border: 1px solid #4b555d;
    border-radius: 5px;
    min-height: 30px;
    padding: 3px 8px;
    font-size: 14px;
    font-weight: 700;
}

QComboBox:hover {
    border-color: #6b7881;
}

QComboBox QAbstractItemView {
    background: #252a2e;
    color: #edf1f2;
    border: 1px solid #515b62;
    selection-background-color: #197987;
}

QRadioButton {
    color: #e2e7ea;
    spacing: 8px;
    font-size: 14px;
    font-weight: 600;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
}

QSlider:horizontal {
    min-height: 32px;
    background: transparent;
}

QSlider::groove:horizontal {
    height: 8px;
    border-radius: 4px;
    background: #59636b;
}

QSlider::sub-page:horizontal {
    border-radius: 4px;
    background: #278e9b;
}

QSlider::handle:horizontal {
    width: 22px;
    height: 22px;
    margin: -7px 0;
    border: 2px solid #e6fbfd;
    border-radius: 11px;
    background: #3bc2d0;
}

QSlider#SliceSlider:vertical {
    min-width: 26px;
    background: transparent;
}

QSlider#SliceSlider::groove:vertical {
    width: 10px;
    background: #59636b;
    border: 1px solid #7a858d;
    border-radius: 5px;
}

QSlider#SliceSlider::sub-page:vertical {
    background: #278e9b;
    border-radius: 5px;
}

QSlider#SliceSlider::handle:vertical {
    height: 24px;
    margin: 0 -8px;
    border: 2px solid #e6fbfd;
    border-radius: 12px;
    background: #3bc2d0;
}

QSlider#SliceSlider::handle:vertical:disabled {
    border-color: #8d969c;
    background: #626b72;
}

QFrame#SliceSliderFrame {
    background: #252a2e;
    border: 1px solid #444d54;
    border-radius: 11px;
}

QWidget#ImagingWorkspace, QFrame#ViewerFrame {
    background: #101214;
}

QFrame#ViewerFrame {
    border: none;
}

QLabel#ViewerTitle {
    background: transparent;
    color: #dce2e5;
    font-size: 12px;
    font-weight: 800;
}

QTextEdit#LogBox {
    background: #121416;
    color: #dce2e5;
    border: 1px solid #3e464c;
    border-radius: 6px;
    padding: 7px;
    font-size: 13px;
    font-weight: 600;
}

QStatusBar {
    background: #181b1e;
    color: #9faab1;
    border-top: 1px solid #343b40;
}
"""
