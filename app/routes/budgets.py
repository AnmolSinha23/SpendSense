"""
SpendSense - Budgeting & Expenditure Control Route
Allows setting category-specific monthly budget ceilings, monitoring expenditure,
and flagging categories approaching (>80%) or exceeding (100%+) limits using
the database view `view_monthly_budget_status`.
"""

from decimal import Decimal
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db import query_db
from app.routes.auth import login_required

budgets_bp = Blueprint('budgets', __name__)


@budgets_bp.route('/budgets')
@login_required
def list_budgets():
    """
    Renders the monthly budget management view.
    Retrieves aggregated budget status from `view_monthly_budget_status`.
    """
    user_id = session['user_id']
    now = datetime.now()

    # Read selected month/year filter (defaults to current)
    try:
        selected_month = int(request.args.get('month', now.month))
        selected_year = int(request.args.get('year', now.year))
    except ValueError:
        selected_month = now.month
        selected_year = now.year

    # Query the analytical database view
    budgets = query_db(
        """
        SELECT
            budget_id,
            category_id,
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

    # Aggregated totals
    total_budgeted = sum(b['budget_amount'] for b in budgets) if budgets else Decimal('0.00')
    total_spent = sum(b['actual_spent'] for b in budgets) if budgets else Decimal('0.00')
    over_budget_count = sum(1 for b in budgets if b['budget_status'] == 'EXCEEDED')
    warning_count = sum(1 for b in budgets if b['budget_status'] == 'WARNING')

    # Available expense categories for setting a new budget
    categories = query_db(
        """
        SELECT category_id, category_name, icon
        FROM categories
        WHERE (user_id IS NULL OR user_id = %s)
          AND category_type = 'expense'
        ORDER BY category_name ASC
        """,
        (user_id,)
    )

    months_list = [
        (1, "January"), (2, "February"), (3, "March"), (4, "April"),
        (5, "May"), (6, "June"), (7, "July"), (8, "August"),
        (9, "September"), (10, "October"), (11, "November"), (12, "December")
    ]

    return render_template(
        'budgets.html',
        budgets=budgets,
        categories=categories,
        total_budgeted=total_budgeted,
        total_spent=total_spent,
        over_budget_count=over_budget_count,
        warning_count=warning_count,
        selected_month=selected_month,
        selected_year=selected_year,
        months_list=months_list,
        current_year=now.year
    )


@budgets_bp.route('/budgets/set', methods=['POST'])
@login_required
def set_budget():
    """
    Sets or updates a monthly budget for a category using MySQL's UPSERT syntax:
    INSERT INTO ... ON DUPLICATE KEY UPDATE budget_amount = VALUES(budget_amount).
    """
    user_id = session['user_id']
    category_id = request.form.get('category_id')
    budget_amount_str = request.form.get('budget_amount', '').strip()
    month = request.form.get('month')
    year = request.form.get('year')

    if not category_id or not budget_amount_str or not month or not year:
        flash("All fields are required to set a budget.", "danger")
        return redirect(url_for('budgets.list_budgets'))

    try:
        budget_amount = Decimal(budget_amount_str)
        if budget_amount <= 0:
            flash("Budget amount must be greater than zero.", "danger")
            return redirect(url_for('budgets.list_budgets', month=month, year=year))

        # Atomic UPSERT query
        query_db(
            """
            INSERT INTO budgets (user_id, category_id, budget_amount, month, year)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE budget_amount = VALUES(budget_amount)
            """,
            (user_id, category_id, budget_amount, int(month), int(year)),
            commit=True
        )

        flash("Budget target saved successfully!", "success")
    except Exception as e:
        flash(f"Error saving budget: {str(e)}", "danger")

    return redirect(url_for('budgets.list_budgets', month=month, year=year))


@budgets_bp.route('/budgets/<int:budget_id>/delete', methods=['POST'])
@login_required
def delete_budget(budget_id):
    """
    Deletes a category budget entry.
    """
    user_id = session['user_id']
    month = request.form.get('month')
    year = request.form.get('year')

    try:
        query_db(
            "DELETE FROM budgets WHERE budget_id = %s AND user_id = %s",
            (budget_id, user_id),
            commit=True
        )
        flash("Budget removed.", "info")
    except Exception as e:
        flash(f"Error deleting budget: {str(e)}", "danger")

    return redirect(url_for('budgets.list_budgets', month=month, year=year))
