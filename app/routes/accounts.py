"""
SpendSense - Accounts Management Route
Handles CRUD operations for user financial accounts (Cash, Bank, Credit Card, UPI, etc.)
with live balances maintained by database triggers.
"""

from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db import query_db, get_db
from app.routes.auth import login_required

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/accounts')
@login_required
def list_accounts():
    """
    Displays all accounts belonging to the user with aggregate inflows and outflows.
    Uses view_account_financial_summary.
    """
    user_id = session['user_id']
    accounts = query_db(
        """
        SELECT
            account_id,
            account_name,
            account_type,
            current_balance,
            total_inflow,
            total_outflow,
            total_transactions
        FROM view_account_financial_summary
        WHERE user_id = %s
        ORDER BY current_balance DESC
        """,
        (user_id,)
    )

    total_net_worth = sum(acc['current_balance'] for acc in accounts) if accounts else Decimal('0.00')

    return render_template(
        'accounts.html',
        accounts=accounts,
        total_net_worth=total_net_worth
    )


@accounts_bp.route('/accounts/add', methods=['POST'])
@login_required
def add_account():
    """
    Creates a new financial account for the user.
    If an initial balance is specified, records an initial deposit transaction.
    """
    user_id = session['user_id']
    account_name = request.form.get('account_name', '').strip()
    account_type = request.form.get('account_type', 'Bank').strip()
    initial_balance_str = request.form.get('initial_balance', '0.00').strip()

    if not account_name:
        flash("Account name is required.", "danger")
        return redirect(url_for('accounts.list_accounts'))

    try:
        initial_balance = Decimal(initial_balance_str)
    except Exception:
        flash("Invalid initial balance format.", "danger")
        return redirect(url_for('accounts.list_accounts'))

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Insert account record
        cursor.execute(
            """
            INSERT INTO accounts (user_id, account_name, account_type, balance)
            VALUES (%s, %s, %s, 0.00)
            """,
            (user_id, account_name, account_type)
        )
        new_account_id = cursor.lastrowid

        # If opening balance is positive, insert an opening balance transaction
        # Trigger trg_after_transaction_insert will automatically adjust the balance!
        if initial_balance > 0:
            # Find or fallback to 'Other Income' category
            cursor.execute(
                "SELECT category_id FROM categories WHERE category_name = 'Other Income' LIMIT 1"
            )
            cat_row = cursor.fetchone()
            cat_id = cat_row['category_id'] if cat_row else 1

            from datetime import date
            cursor.execute(
                """
                INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description)
                VALUES (%s, %s, %s, %s, 'income', %s, 'Initial Opening Balance')
                """,
                (user_id, new_account_id, cat_id, initial_balance, date.today())
            )

        db.commit()
        cursor.close()

        flash(f"Account '{account_name}' created successfully!", "success")
    except Exception as e:
        flash(f"Error creating account: {str(e)}", "danger")

    return redirect(url_for('accounts.list_accounts'))


@accounts_bp.route('/accounts/<int:account_id>/edit', methods=['POST'])
@login_required
def edit_account(account_id):
    """
    Updates the name or type of an existing account.
    """
    user_id = session['user_id']
    account_name = request.form.get('account_name', '').strip()
    account_type = request.form.get('account_type', 'Bank').strip()

    if not account_name:
        flash("Account name cannot be empty.", "danger")
        return redirect(url_for('accounts.list_accounts'))

    try:
        query_db(
            """
            UPDATE accounts
            SET account_name = %s, account_type = %s
            WHERE account_id = %s AND user_id = %s
            """,
            (account_name, account_type, account_id, user_id),
            commit=True
        )
        flash("Account updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating account: {str(e)}", "danger")

    return redirect(url_for('accounts.list_accounts'))


@accounts_bp.route('/accounts/<int:account_id>/delete', methods=['POST'])
@login_required
def delete_account(account_id):
    """
    Deletes an account and cascades deletions to linked transactions.
    """
    user_id = session['user_id']
    try:
        query_db(
            "DELETE FROM accounts WHERE account_id = %s AND user_id = %s",
            (account_id, user_id),
            commit=True
        )
        flash("Account and its linked transactions have been deleted.", "info")
    except Exception as e:
        flash(f"Error deleting account: {str(e)}", "danger")

    return redirect(url_for('accounts.list_accounts'))
