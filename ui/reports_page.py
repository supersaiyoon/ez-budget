from PyQt6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ui.helpers import money_item


class ReportsPage(QWidget):
    def __init__(self, budgets):
        super().__init__()
        self.budgets = budgets

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Reports")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        description = QLabel("Sample monthly report data")
        description.setObjectName("statusText")
        layout.addWidget(description)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Month", "Income", "Budgeted", "Spent", "Remaining"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(len(self.budgets))
        for row, budget in enumerate(self.budgets):
            self.table.setItem(row, 0, QTableWidgetItem(budget.month_name))
            self.table.setItem(row, 1, money_item(budget.monthly_income))
            self.table.setItem(row, 2, money_item(budget.total_budgeted))
            self.table.setItem(row, 3, money_item(budget.total_spent))
            self.table.setItem(row, 4, money_item(budget.total_remaining))
