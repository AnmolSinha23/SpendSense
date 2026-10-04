"""
SpendSense - Dashboard Route
Aggregates financial statistics, recent activity, live account balances,
and budget warning alerts using raw SQL queries and database views.
"""

from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for, request
from app.db import query_db
from app.routes.auth import login_required

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """
    Renders the central financial dashboard.
    Retrieves real-time totals, segregated assets & liabilities,
    recent transaction feed, interactive month stepper, and budget progress.
    """
    user_id = session['user_id']
    now = datetime.now()

    # 1. Month Stepper Parameter Handling
    month_arg = request.args.get('month', type=int)
    year_arg = request.args.get('year', type=int)

    if month_arg and 1 <= month_arg <= 12 and year_arg and 2000 <= year_arg <= 2100:
        selected_month = month_arg
        selected_year = year_arg
    else:
        selected_month = now.month
        selected_year = now.year

    # Previous and Next Month calculations
    if selected_month == 1:
        prev_month, prev_year = 12, selected_year - 1
    else:
        prev_month, prev_year = selected_month - 1, selected_year

    if selected_month == 12:
        next_month, next_year = 1, selected_year + 1
    else:
        next_month, next_year = selected_month + 1, selected_year

    selected_date = datetime(selected_year, selected_month, 1)
    selected_month_name = selected_date.strftime("%B")

    # 2. Selected Month's Income
    income_res = query_db(
        """
        SELECT COALESCE(SUM(amount), 0.00) AS total_income
        FROM transactions
        WHERE user_id = %s AND txn_type = 'income'
          AND MONTH(txn_date) = %s AND YEAR(txn_date) = %s
        """,
        (user_id, selected_month, selected_year),
        one=True
    )
    monthly_income = float(income_res['total_income'] if income_res else 0.0)

    # 3. Selected Month's Expenses
    expense_res = query_db(
        """
        SELECT COALESCE(SUM(amount), 0.00) AS total_expense
        FROM transactions
        WHERE user_id = %s AND txn_type = 'expense'
          AND MONTH(txn_date) = %s AND YEAR(txn_date) = %s
        """,
        (user_id, selected_month, selected_year),
        one=True
    )
    monthly_expense = float(expense_res['total_expense'] if expense_res else 0.0)

    # 4. Net Monthly Cashflow (Savings / Deficit)
    monthly_cashflow = monthly_income - monthly_expense

    # 5. Accounts: Segregate Liquid Assets from Credit Liabilities
    accounts = query_db(
        "SELECT * FROM accounts WHERE user_id = %s ORDER BY balance DESC",
        (user_id,)
    )

    liquid_accounts = []
    liability_accounts = []
    total_liquid_cash = 0.0
    total_liabilities = 0.0

    for acc in accounts:
        bal = float(acc['balance'] or 0.0)
        acc_type = str(acc['account_type'] or '').strip()

        if acc_type in ('Credit Card', 'Loan') or bal < 0:
            due = abs(bal) if bal < 0 else 0.0
            acc_data = dict(acc)
            acc_data['outstanding_due'] = due
            liability_accounts.append(acc_data)
            total_liabilities += due
        else:
            liquid_accounts.append(acc)
            total_liquid_cash += bal

    total_net_worth = total_liquid_cash - total_liabilities

    # 6. Recent Transactions (JOINed with accounts & categories)
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
        LIMIT 8
        """,
        (user_id,)
    )

    # 7. Budgets for Selected Month (All configured budgets for progress meters)
    all_budgets = query_db(
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
        WHERE user_id = %s AND month = %s AND year = %s
        ORDER BY percentage_used DESC
        """,
        (user_id, selected_month, selected_year)
    )

    budget_alerts = [b for b in all_budgets if b['budget_status'] in ('WARNING', 'EXCEEDED')]

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
        selected_month=selected_month,
        selected_year=selected_year,
        selected_month_name=selected_month_name,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        monthly_cashflow=monthly_cashflow,
        total_net_worth=total_net_worth,
        total_liquid_cash=total_liquid_cash,
        total_liabilities=total_liabilities,
        liquid_accounts=liquid_accounts,
        liability_accounts=liability_accounts,
        recent_transactions=recent_transactions,
        all_budgets=all_budgets,
        budget_alerts=budget_alerts,
        accounts=accounts,
        categories=categories,
        today_date=now.strftime("%Y-%m-%d"),
        is_current_month=(selected_month == now.month and selected_year == now.year)
    )
