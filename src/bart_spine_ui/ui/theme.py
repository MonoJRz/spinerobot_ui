APP_STYLESHEET = r"""
QMainWindow, QWidget#AppRoot {
    background: #0b1014;
    color: #dce4e9;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #dce4e9;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 13px;
}

QFrame#TopBar {
    background: #101820;
    border: none;
    border-bottom: 1px solid #29465a;
}

QLabel#BrandTitle {
    background: transparent;
    color: #eef4f6;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 25px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#BrandSubtitle {
    background: transparent;
    color: #8fa9b9;
    font-size: 9px;
}

QPushButton#StageButton {
    background: #121d25;
    color: #9dbbd0;
    border: 1px solid #29475b;
    border-radius: 0;
    min-width: 145px;
    min-height: 48px;
    padding: 0 18px;
    font-size: 16px;
    font-weight: 700;
}

QPushButton#StageButton:first {
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
}

QPushButton#StageButton:hover {
    background: #182932;
    color: #dcecf3;
}

QPushButton#StageButton:checked {
    background: #126f72;
    border: 1px solid #35c6c0;
    color: white;
}

QPushButton#UtilityButton {
    background: transparent;
    color: #92bed8;
    border: none;
    border-radius: 18px;
    min-width: 38px;
    min-height: 38px;
    font-size: 22px;
    font-weight: 700;
}

QPushButton#UtilityButton:hover {
    background: #1b2a33;
    color: #c8e8f5;
}

QFrame#HeaderDivider {
    background: #365164;
    min-width: 1px;
    max-width: 1px;
    min-height: 42px;
    max-height: 42px;
}

QLabel#HeaderMeta, QLabel#HeaderTime, QLabel#RoomLabel {
    background: transparent;
    color: #a8c2d3;
}

QLabel#HeaderMeta {
    font-size: 11px;
}

QLabel#HeaderTime {
    color: #d5e8f2;
    font-size: 15px;
    font-weight: 700;
}

QLabel#RoomLabel {
    font-size: 15px;
    font-weight: 700;
}

QFrame#LeftSidebar, QFrame#RightSidebar {
    background: #0b1014;
    border: none;
}

QFrame#SidebarCard {
    background: #141b20;
    border: 1px solid #2b5068;
    border-radius: 8px;
}

QFrame#SidebarCard QLabel,
QFrame#SidebarCard QRadioButton {
    background: transparent;
}

QLabel#CardTitle {
    color: #dce9f0;
    font-size: 14px;
    font-weight: 800;
}

QFrame#CardDivider {
    background: #294356;
    min-height: 1px;
    max-height: 1px;
}

QPushButton#PrimaryAction, QPushButton#SecondaryAction {
    color: white;
    border-radius: 7px;
    min-height: 48px;
    padding: 0 12px;
    font-size: 15px;
    font-weight: 800;
}

QPushButton#PrimaryAction {
    background: #176d99;
    border: 1px solid #41aadb;
}

QPushButton#SecondaryAction {
    background: #183a52;
    border: 1px solid #315f7d;
}

QPushButton#PrimaryAction:hover, QPushButton#SecondaryAction:hover {
    background: #2184b4;
    border-color: #63c4ec;
}

QPushButton#CardAction {
    background: #1a3040;
    color: #bed8e8;
    border: 1px solid #345a72;
    border-radius: 5px;
    min-height: 28px;
    padding: 0 9px;
    font-size: 12px;
}

QPushButton#CardAction:hover {
    background: #23485e;
    color: white;
}

QLabel#SidebarText, QLabel#SidebarValue {
    color: #d5e0e5;
    font-size: 13px;
}

QLabel#SidebarValue {
    font-weight: 800;
}

QLabel#RangeText, QLabel#StatusTime, QLabel#CaseKey {
    color: #8ea9ba;
    font-size: 12px;
}

QLabel#StatusGroup {
    color: #d4e0e6;
    font-size: 12px;
    font-weight: 800;
}

QLabel#CaseValue {
    color: #e2e9ed;
    font-size: 13px;
}

QLabel#StatusOk, QLabel#StatusWarn, QLabel#StatusError, QLabel#StatusWaiting {
    font-weight: 700;
    font-size: 13px;
}

QLabel#StatusOk {
    color: #58d481;
}

QLabel#StatusWarn {
    color: #e8bd5d;
}

QLabel#StatusError {
    color: #ef6e69;
}

QLabel#StatusWaiting {
    color: #91a6b3;
}

QComboBox {
    background: #111a20;
    color: #e3ebef;
    border: 1px solid #35566b;
    border-radius: 5px;
    min-height: 32px;
    padding: 3px 8px;
    font-size: 13px;
    font-weight: 700;
}

QComboBox:hover {
    border-color: #5383a0;
}

QComboBox QAbstractItemView {
    background: #161e23;
    color: #e3ebef;
    border: 1px solid #41657b;
    selection-background-color: #176d99;
}

QRadioButton {
    color: #d1dce2;
    spacing: 7px;
    font-size: 13px;
}

QRadioButton::indicator {
    width: 17px;
    height: 17px;
}

QSlider:horizontal {
    min-height: 30px;
    background: transparent;
}

QSlider::groove:horizontal {
    height: 6px;
    border-radius: 3px;
    background: #345063;
}

QSlider::sub-page:horizontal {
    border-radius: 3px;
    background: #1b91d1;
}

QSlider::handle:horizontal {
    width: 20px;
    height: 20px;
    margin: -7px 0;
    border: 2px solid #e9f8ff;
    border-radius: 10px;
    background: #249fe0;
}

QSlider#SliceSlider:vertical {
    min-width: 26px;
    background: transparent;
}

QSlider#SliceSlider::groove:vertical {
    width: 10px;
    background: #304a5b;
    border: 1px solid #55758a;
    border-radius: 5px;
}

QSlider#SliceSlider::sub-page:vertical {
    background: #167fb9;
    border-radius: 5px;
}

QSlider#SliceSlider::handle:vertical {
    height: 24px;
    margin: 0 -8px;
    border: 2px solid #e8f7ff;
    border-radius: 12px;
    background: #249fe0;
}

QSlider#SliceSlider::handle:vertical:disabled {
    border-color: #71838e;
    background: #4a5962;
}

QWidget#ImagingWorkspace {
    background: #080d10;
}

QFrame#ViewerFrame {
    background: #10171c;
    border: 1px solid #294b61;
    border-radius: 8px;
}

QFrame#ViewerFrame QLabel {
    background: transparent;
}

QFrame#SliceSliderFrame {
    background: #111a20;
    border: 1px solid #294a60;
    border-radius: 9px;
}

QLabel#ViewerIcon {
    color: #76b7dc;
    font-size: 19px;
    font-weight: 800;
}

QLabel#ViewerTitle {
    color: #e4ebef;
    font-size: 14px;
    font-weight: 800;
}

QLabel#ViewerMeta {
    color: #8eb5ca;
    font-size: 11px;
}

QPushButton#ViewerToolButton {
    background: #162734;
    color: #9bc9e3;
    border: 1px solid #2d536b;
    border-radius: 5px;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    font-size: 17px;
    font-weight: 700;
}

QPushButton#ViewerToolButton:hover {
    background: #20445a;
    color: white;
    border-color: #4c83a2;
}

QTextEdit#LogBox {
    background: #0d1317;
    color: #bcd0dc;
    border: none;
    padding: 5px;
    font-size: 12px;
}

QScrollBar:vertical {
    background: #10171c;
    width: 9px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3d5a6c;
    border-radius: 4px;
    min-height: 28px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}


QDialog#CaseEditor {
    background: #141b20;
    color: #dce4e9;
}

QDialog#CaseEditor QLabel {
    background: transparent;
    color: #a9c0ce;
    font-size: 13px;
}

QLineEdit#CaseField {
    background: #0d1418;
    color: #e4edf1;
    border: 1px solid #365a70;
    border-radius: 5px;
    min-height: 32px;
    padding: 3px 8px;
    selection-background-color: #176d99;
}

QLineEdit#CaseField:focus {
    border-color: #42a9d6;
}

QDialogButtonBox QPushButton {
    background: #183a52;
    color: #e7f0f4;
    border: 1px solid #37617c;
    border-radius: 5px;
    min-width: 86px;
    min-height: 32px;
    font-weight: 700;
}

QDialogButtonBox QPushButton:hover {
    background: #176d99;
    border-color: #55b8df;
}

QFrame#FooterBar {
    background: #10171c;
    border: none;
    border-top: 1px solid #29465a;
}

QLabel#FooterMeta {
    background: transparent;
    color: #9bb4c3;
    font-size: 12px;
}

QLabel#FooterWaiting, QLabel#FooterReady, QLabel#FooterWarning {
    background: transparent;
    font-size: 13px;
    font-weight: 800;
}

QLabel#FooterWaiting {
    color: #8fa8b7;
}

QLabel#FooterReady {
    color: #58d481;
}

QLabel#FooterWarning {
    color: #e8bd5d;
}
"""
