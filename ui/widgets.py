from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QSizePolicy, QWidget


VISIBLE_MONTHS = 2
VISIBLE_SCROLLER_MONTHS = 5


class MonthScroller(QWidget):
    def __init__(self, on_month_selected):
        super().__init__()
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.on_month_selected = on_month_selected
        self.buttons = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.previous_button = QPushButton("<")
        self.previous_button.setObjectName("monthArrow")
        self.previous_button.clicked.connect(lambda: self.shift_months(-1))
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
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.next_button = QPushButton(">")
        self.next_button.setObjectName("monthArrow")
        self.next_button.clicked.connect(lambda: self.shift_months(1))
        layout.addWidget(self.next_button)

    def shift_months(self, direction):
        active_index = next((button.property("budget_index") for button in self.buttons if button.property("active")), 0)
        self.on_month_selected(active_index + direction)

    def set_months(self, indexed_budgets, active_index):
        while len(self.buttons) > len(indexed_budgets):
            button = self.buttons.pop()
            self.scroll_layout.removeWidget(button)
            button.deleteLater()

        for index in range(len(self.buttons), len(indexed_budgets)):
            button = QPushButton()
            button.setObjectName("monthButton")
            self.scroll_layout.addWidget(button)
            self.buttons.append(button)

        for button, (budget_index, budget) in zip(self.buttons, indexed_budgets):
            button.setText(budget.month_name)
            button.setProperty("budget_index", budget_index)
            try:
                button.clicked.disconnect()
            except TypeError:
                pass
            button.clicked.connect(lambda checked=False, index=budget_index: self.on_month_selected(index))
            button.setProperty("active", budget_index == active_index)
            button.style().unpolish(button)
            button.style().polish(button)
