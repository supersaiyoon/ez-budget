from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QSizePolicy, QWidget


VISIBLE_MONTHS = 2


class MonthScroller(QWidget):
    def __init__(self, budgets, on_month_selected):
        super().__init__()
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.budgets = budgets
        self.on_month_selected = on_month_selected
        self.buttons = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.previous_button = QPushButton("<")
        self.previous_button.setObjectName("monthArrow")
        self.previous_button.clicked.connect(partial(self.shift_months, -1))
        layout.addWidget(self.previous_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(36)

        scroll_content = QWidget()
        self.scroll_layout = QHBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(3, 3, 3, 3)
        self.scroll_layout.setSpacing(4)
        self.sync_buttons()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.next_button = QPushButton(">")
        self.next_button.setObjectName("monthArrow")
        self.next_button.clicked.connect(partial(self.shift_months, 1))
        layout.addWidget(self.next_button)

    def shift_months(self, direction):
        active_index = next((index for index, button in enumerate(self.buttons) if button.property("active")), 0)
        self.on_month_selected(active_index + direction)

    def sync_buttons(self):
        for index in range(len(self.buttons), len(self.budgets)):
            button = QPushButton(self.budgets[index].month_name)
            button.setObjectName("monthButton")
            button.clicked.connect(partial(self.on_month_selected, index))
            self.scroll_layout.addWidget(button)
            self.buttons.append(button)

    def set_active_months(self, start_index):
        for index, button in enumerate(self.buttons):
            button.setProperty("active", start_index <= index < start_index + VISIBLE_MONTHS)
            button.style().unpolish(button)
            button.style().polish(button)
