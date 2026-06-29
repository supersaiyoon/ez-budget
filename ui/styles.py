APP_STYLE = """
/* Light app background keeps dense tables from feeling boxed in. */
QMainWindow {
    background: #f5f7f9;
}
/* Dark rail gives page navigation clear separation from work area. */
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
/* Selected item needs stronger contrast than hover-only navigation. */
#navList::item:selected {
    background: #3f5f7a;
}
/* Shared title styling keeps every page on same visual hierarchy. */
#pageTitle {
    font-size: 28px;
    font-weight: 700;
    color: #1f2933;
}
#statusText {
    color: #4d5b6a;
}
/* Month buttons use dynamic active property from MonthScroller. */
#monthButton {
    background: #ffffff;
    color: #26323f;
    border: 1px solid #c8d1dc;
    border-radius: 4px;
    padding: 5px 12px;
}
/* Active month has filled treatment so it reads like current context. */
#monthButton[active="true"] {
    background: #2f6f8f;
    color: #ffffff;
    border-color: #2f6f8f;
}
/* Fixed arrow width prevents scroller layout from shifting. */
#monthArrow {
    min-width: 36px;
    max-width: 36px;
    padding: 5px 0;
}
/* Border around scroll area makes month strip read as one control. */
QScrollArea {
    border: 1px solid #d8dee6;
    background: #ffffff;
}
/* Table colors kept quiet so money values stay primary. */
QTableWidget {
    background: #ffffff;
    border: 1px solid #d8dee6;
    gridline-color: #e5e9ef;
    alternate-background-color: #f8fafc;
}
/* Header weight helps separate labels from editable cells. */
QHeaderView::section {
    background: #eef2f6;
    color: #1f2933;
    border: 0;
    border-right: 1px solid #d8dee6;
    padding: 8px;
    font-weight: 700;
}
/* Inputs match table density without looking like standalone forms. */
QLineEdit {
    padding: 5px 7px;
    border: 1px solid #b8c2cc;
    border-radius: 4px;
}
/* Buttons share app accent so actions and active month feel related. */
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
