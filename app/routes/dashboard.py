"""
SpendSense - Dashboard Route
Aggregates financial statistics, recent activity, live account balances,
and budget warning alerts using raw SQL queries and database views.
"""

from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for
from app.db import query_db
from app.routes.auth import login_required

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """
    Renders the central financial dashboard.
    Retrieves real-time totals, account balances, recent transactions,
    and budget status indicators.
    """
    user_id = session['user_id']
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    # 1. Total Net Worth across all accounts
    net_worth_res = query_db(
        "SELECT COALESCE(SUM(balance), 0.00) AS total_balance FROM accounts WHERE user_id = %s",
        (user_id,),
        one=True
    )
    total_balance = net_worth_res['total_balance'] if net_worth_res else 0.00

    # 2. Current Month's Income
    income_res = query_db(
        """
        SELECT COALESCE(SUM(amount), 0.00) AS total_income
        FROM transactions
        WHERE user_id = %s AND txn_type = 'income'
          AND MONTH(txn_date) = %s AND YEAR(txn_date) = %s
        """,
        (user_id, current_month, current_year),
        one=True
    )
    monthly_income = income_res['total_income'] if income_res else 0.00

    # 3. Current Month's Expenses
    expense_res = query_db(
        """
        SELECT COALESCE(SUM(amount), 0.00) AS total_expense
        FROM transactions
        WHERE user_id = %s AND txn_type = 'expense'
          AND MONTH(txn_date) = %s AND YEAR(txn_date) = %s
        """,
        (user_id, current_month, current_year),
        one=True
    )
    monthly_expense = expense_res['total_expense'] if expense_res else 0.00

    # 4. Net Monthly Savings
    monthly_savings = monthly_income - monthly_expense

    # 5. User Financial Accounts with live balances
    accounts = query_db(
        "SELECT * FROM accounts WHERE user_id = %s ORDER BY balance DESC",
        (user_id,)
    )

    # 6. Recent 6 Transactions (JOINed with accounts & categories)
    recent_transactions = query_db(
        """
        SELECT
            t.transaction_id,
            t.amount,
            t.txn_type,
            t.txn_date,
            t.description,
            a.account_name,
            c.category_name,
            c.icon AS category_icon
        FROM transactions t
        INNER JOIN accounts a ON t.account_id = a.account_id
        INNER JOIN categories c ON t.category_id = c.category_id
        WHERE t.user_id = %s
        ORDER BY t.txn_date DESC, t.transaction_id DESC
        LIMIT 6
        """,
        (user_id,)
    )

    # 7. Budget Alerts for current month (Querying the Database View)
    budget_alerts = query_db(
        """
        SELECT
            category_name,
            category_icon,
            budget_amount,
            actual_spent,
            remaining_budget,
            percentage_used,
            budget_status
        FROM view_monthly_budget_status
        WHERE user_id = %s AND month = %s AND year = %s AND budget_status IN ('WARNING', 'EXCEEDED')
        ORDER BY percentage_used DESC
        """,
        (user_id, current_month, current_year)
    )

    # 8. Available categories for quick transaction modal
    categories = query_db(
        """
        SELECT category_id, category_name, category_type, icon
        FROM categories
        WHERE user_id IS NULL OR user_id = %s
        ORDER BY category_type DESC, category_name ASC
        """,
        (user_id,)
    )

    return render_template(
        'dashboard.html',
        total_balance=total_balance,
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        monthly_savings=monthly_savings,
        accounts=accounts,
        recent_transactions=recent_transactions,
        budget_alerts=budget_alerts,
        categories=categories,
        current_month_name=now.strftime("%B"),
        current_year=current_year,
        today_date=now.strftime("%Y-%m-%d")
    )
