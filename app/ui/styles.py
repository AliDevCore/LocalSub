"""
LocalSub - Application Stylesheet and Visual Theme.
Modern, clean Windows 11 Fluent-inspired theme with subtle borders,
high-contrast accessible text, and pleasant status colors.
"""

APP_STYLESHEET = """
/* Global Window and Base Controls */
QMainWindow, QWidget#CentralWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Tahoma", sans-serif;
    font-size: 13px;
}

QGroupBox {
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 18px;
    padding-bottom: 10px;
    padding-left: 10px;
    padding-right: 10px;
    background-color: #1e293b;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background-color: #1e293b;
    color: #38bdf8;
}

/* Labels */
QLabel {
    color: #cbd5e1;
}

QLabel#HeaderTitle {
    font-size: 20px;
    font-weight: 700;
    color: #f8fafc;
}

QLabel#HeaderSubtitle {
    font-size: 13px;
    color: #94a3b8;
}

QLabel#StatusBadgeReady {
    background-color: #065f46;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 600;
    font-size: 11px;
}

QLabel#StatusBadgeMissing {
    background-color: #854d0e;
    color: #fde047;
    border: 1px solid #ca8a04;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 600;
    font-size: 11px;
}

QLabel#StatusBadgeNeutral {
    background-color: #334155;
    color: #94a3b8;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 600;
    font-size: 11px;
}

/* Combo Boxes */
QComboBox {
    background-color: #0f172a;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f8fafc;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #38bdf8;
}

QComboBox:focus {
    border-color: #0284c7;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #475569;
    color: #f8fafc;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
    padding: 4px;
}

/* Line Edit */
QLineEdit {
    background-color: #0f172a;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f8fafc;
    min-height: 20px;
}

QLineEdit:focus {
    border-color: #38bdf8;
}

/* Push Buttons */
QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #475569;
    border-color: #64748b;
}

QPushButton:pressed {
    background-color: #1e293b;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

QPushButton#PrimaryButton {
    background-color: #0284c7;
    color: #ffffff;
    border: 1px solid #0369a1;
}

QPushButton#PrimaryButton:hover {
    background-color: #0ea5e9;
    border-color: #38bdf8;
}

QPushButton#PrimaryButton:pressed {
    background-color: #0369a1;
}

QPushButton#CancelButton {
    background-color: #dc2626;
    color: #ffffff;
    border: 1px solid #b91c1c;
}

QPushButton#CancelButton:hover {
    background-color: #ef4444;
}

QPushButton#CancelButton:pressed {
    background-color: #b91c1c;
}

/* Table Widget */
QTableWidget {
    background-color: #0f172a;
    alternate-background-color: #162033;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #f8fafc;
    gridline-color: #1e293b;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 6px 8px;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #334155;
    font-weight: 600;
}

/* Progress Bars */
QProgressBar {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 5px;
    text-align: center;
    color: #f8fafc;
    font-size: 11px;
    font-weight: 600;
    min-height: 14px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 4px;
}

/* Checkboxes */
QCheckBox {
    color: #cbd5e1;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #475569;
    border-radius: 3px;
    background-color: #0f172a;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
