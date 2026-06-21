APP_STYLE = """
QMainWindow {
    background: #f5f7f9;
}
#navList {
    background: #26323f;
    color: #f7fafc;
    border: 0;
    padding-top: 14px;
    font-size: 15px;
}
#navList::item {
    padding: 14px 18px;
}
#navList::item:selected {
    background: #3f5f7a;
}
#pageTitle {
    font-size: 28px;
    font-weight: 700;
    color: #1f2933;
}
#statusText {
    color: #4d5b6a;
}
#monthButton {
    background: #ffffff;
    color: #26323f;
    border: 1px solid #c8d1dc;
    border-radius: 4px;
    padding: 5px 12px;
}
#monthButton[active="true"] {
    background: #2f6f8f;
    color: #ffffff;
    border-color: #2f6f8f;
}
#monthArrow {
    min-width: 36px;
    max-width: 36px;
    padding: 5px 0;
}
QScrollArea {
    border: 1px solid #d8dee6;
    background: #ffffff;
}
QTableWidget {
    background: #ffffff;
    border: 1px solid #d8dee6;
    gridline-color: #e5e9ef;
    alternate-background-color: #f8fafc;
}
QHeaderView::section {
    background: #eef2f6;
    color: #1f2933;
    border: 0;
    border-right: 1px solid #d8dee6;
    padding: 8px;
    font-weight: 700;
}
QLineEdit {
    padding: 5px 7px;
    border: 1px solid #b8c2cc;
    border-radius: 4px;
}
QPushButton {
    padding: 6px 10px;
    background: #2f6f8f;
    color: white;
    border: 0;
    border-radius: 4px;
}
QPushButton:hover {
    background: #255d78;
}
"""
