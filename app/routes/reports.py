"""
SpendSense - Reports and Analytics Route
Powers the interactive Chart.js visualizations (Category Pie Chart, Monthly Trend Bar Chart)
and provides CSV data export using analytical queries and `view_monthly_category_summary`.
"""

import io
import csv
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, jsonify, make_response, session
from app.db import query_db
from app.routes.auth import login_required

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/reports')
@login_required
def index():
    """
    Renders the visual reports page with interactive Chart.js charts.
    """
    user_id = session['user_id']
    now = datetime.now()

    try:
        selected_month = int(request.args.get('month', now.month))
        selected_year = int(request.args.get('year', now.year))
    except ValueError:
        selected_month = now.month
        selected_year = now.year

    # 1. Category Expense breakdown from the database VIEW
    category_expenses = query_db(
        """
        SELECT
            category_name,
            total_amount,
            category_icon,
            transaction_count,
            avg_transaction_amount
        FROM view_monthly_category_summary
        WHERE user_id = %s AND month = %s AND year = %s AND category_type = 'expense'
        ORDER BY total_amount DESC
        """,
        (user_id, selected_month, selected_year)
    )

    # 2. Category Income breakdown from the database VIEW
    category_incomes = query_db(
        """
        SELECT
            category_name,
            total_amount,
            category_icon,
            transaction_count,
            avg_transaction_amount
        FROM view_monthly_category_summary
        WHERE user_id = %s AND month = %s AND year = %s AND category_type = 'income'
        ORDER BY total_amount DESC
        """,
        (user_id, selected_month, selected_year)
    )

    # 3. Monthly Trends (Income vs Expense) across the last 6 months
    monthly_trends = query_db(
        """
        SELECT
            DATE_FORMAT(txn_date, '%Y-%m') AS ym_key,
            DATE_FORMAT(txn_date, '%b %Y') AS month_label,
            COALESCE(SUM(CASE WHEN txn_type = 'income' THEN amount ELSE 0 END), 0.00) AS total_income,
            COALESCE(SUM(CASE WHEN txn_type = 'expense' THEN amount ELSE 0 END), 0.00) AS total_expense
        FROM transactions
        WHERE user_id = %s
          AND txn_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY ym_key, month_label
        ORDER BY ym_key ASC
        """,
        (user_id,)
    )

    # 4. Account balance distribution
    accounts_dist = query_db(
        """
        SELECT account_name, account_type, balance
        FROM accounts
        WHERE user_id = %s AND balance > 0
        ORDER BY balance DESC
        """,
        (user_id,)
    )

    months_list = [
        (1, "January"), (2, "February"), (3, "March"), (4, "April"),
        (5, "May"), (6, "June"), (7, "July"), (8, "August"),
        (9, "September"), (10, "October"), (11, "November"), (12, "December")
    ]

    total_expense = sum(c['total_amount'] for c in category_expenses) if category_expenses else Decimal('0.00')
    total_income = sum(c['total_amount'] for c in category_incomes) if category_incomes else Decimal('0.00')

    return render_template(
        'reports.html',
        category_expenses=category_expenses,
        category_incomes=category_incomes,
        monthly_trends=monthly_trends,
        accounts_dist=accounts_dist,
        selected_month=selected_month,
        selected_year=selected_year,
        months_list=months_list,
        total_expense=total_expense,
        total_income=total_income,
        current_year=now.year
    )


@reports_bp.route('/reports/api/chart-data')
@login_required
def chart_data():
    """
    JSON API endpoint returning data consumed by Chart.js.
    """
    user_id = session['user_id']
    now = datetime.now()

    try:
        month = int(request.args.get('month', now.month))
        year = int(request.args.get('year', now.year))
    except ValueError:
        month = now.month
        year = now.year

    # Expense Category breakdown
    expenses = query_db(
        """
        SELECT category_name, total_amount
        FROM view_monthly_category_summary
        WHERE user_id = %s AND month = %s AND year = %s AND category_type = 'expense'
        ORDER BY total_amount DESC
        """,
        (user_id, month, year)
    )

    # Monthly Trends
    trends = query_db(
        """
        SELECT
            DATE_FORMAT(txn_date, '%b %Y') AS month_label,
            COALESCE(SUM(CASE WHEN txn_type = 'income' THEN amount ELSE 0 END), 0.00) AS income,
            COALESCE(SUM(CASE WHEN txn_type = 'expense' THEN amount ELSE 0 END), 0.00) AS expense
        FROM transactions
        WHERE user_id = %s
          AND txn_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(txn_date, '%Y-%m'), month_label
        ORDER BY DATE_FORMAT(txn_date, '%Y-%m') ASC
        """,
        (user_id,)
    )

    # Account balances
    accounts = query_db(
        "SELECT account_name, balance FROM accounts WHERE user_id = %s AND balance > 0",
        (user_id,)
    )

    return jsonify({
        'expense_categories': {
            'labels': [e['category_name'] for e in expenses],
            'data': [float(e['total_amount']) for e in expenses]
        },
        'monthly_trends': {
            'labels': [t['month_label'] for t in trends],
            'income': [float(t['income']) for t in trends],
            'expense': [float(t['expense']) for t in trends]
        },
        'accounts': {
            'labels': [a['account_name'] for a in accounts],
            'data': [float(a['balance']) for a in accounts]
        }
    })


@reports_bp.route('/reports/export-csv')
@login_required
def export_csv():
    """
    Generates and downloads a CSV spreadsheet containing all user transactions.
    """
    user_id = session['user_id']
    transactions = query_db(
        """
        SELECT
            t.transaction_id,
            t.txn_date,
            t.txn_type,
            c.category_name,
            a.account_name,
            t.amount,
            t.description
        FROM transactions t
        INNER JOIN accounts a ON t.account_id = a.account_id
        INNER JOIN categories c ON t.category_id = c.category_id
        WHERE t.user_id = %s
        ORDER BY t.txn_date DESC, t.transaction_id DESC
        """,
        (user_id,)
    )

    # Generate CSV stream in memory
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Transaction ID', 'Date', 'Type', 'Category', 'Account', 'Amount', 'Description'])

    for t in transactions:
        writer.writerow([
            t['transaction_id'],
            t['txn_date'].strftime("%Y-%m-%d") if hasattr(t['txn_date'], 'strftime') else str(t['txn_date']),
            t['txn_type'].upper(),
            t['category_name'],
            t['account_name'],
            float(t['amount']),
            t['description'] or ''
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=SpendSense_Transactions.csv"
    output.headers["Content-type"] = "text/csv"
    return output
