"""
SpendSense - Transactions Management Route
Handles transaction creation (via MySQL Stored Procedure `sp_add_transaction`),
dynamic search/filtering, editing, and deletion.
Live account balances are automatically updated via MySQL database triggers.
"""

from decimal import Decimal
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db import query_db, get_db
from app.routes.auth import login_required

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/transactions')
@login_required
def list_transactions():
    """
    Renders filtered transaction list with multi-criteria search:
    - Date range (start_date, end_date)
    - Category
    - Account
    - Transaction type (income / expense)
    - Amount range
    - Text search on description
    """
    user_id = session['user_id']

    # Filter parameters from request
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    category_id = request.args.get('category_id', '').strip()
    account_id = request.args.get('account_id', '').strip()
    txn_type = request.args.get('txn_type', '').strip()
    search = request.args.get('search', '').strip()
    min_amount = request.args.get('min_amount', '').strip()
    max_amount = request.args.get('max_amount', '').strip()

    # Base query joined with accounts and categories
    query = """
        SELECT
            t.transaction_id,
            t.amount,
            t.txn_type,
            t.txn_date,
            t.description,
            t.account_id,
            t.category_id,
            a.account_name,
            a.account_type,
            c.category_name,
            c.icon AS category_icon
        FROM transactions t
        INNER JOIN accounts a ON t.account_id = a.account_id
        INNER JOIN categories c ON t.category_id = c.category_id
        WHERE t.user_id = %s
    """
    params = [user_id]

    # Dynamic filter conditions
    if start_date:
        query += " AND t.txn_date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND t.txn_date <= %s"
        params.append(end_date)

    if category_id:
        query += " AND t.category_id = %s"
        params.append(category_id)

    if account_id:
        query += " AND t.account_id = %s"
        params.append(account_id)

    if txn_type in ('income', 'expense'):
        query += " AND t.txn_type = %s"
        params.append(txn_type)

    if search:
        query += " AND (t.description LIKE %s OR c.category_name LIKE %s)"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern])

    if min_amount:
        try:
            query += " AND t.amount >= %s"
            params.append(float(min_amount))
        except ValueError:
            pass

    if max_amount:
        try:
            query += " AND t.amount <= %s"
            params.append(float(max_amount))
        except ValueError:
            pass

    query += " ORDER BY t.txn_date DESC, t.transaction_id DESC"

    transactions = query_db(query, tuple(params))

    # Calculate summary metrics for currently filtered results
    total_income = sum(t['amount'] for t in transactions if t['txn_type'] == 'income') if transactions else Decimal('0.00')
    total_expense = sum(t['amount'] for t in transactions if t['txn_type'] == 'expense') if transactions else Decimal('0.00')
    net_flow = total_income - total_expense

    # Fetch user accounts and categories for modal dropdowns
    accounts = query_db("SELECT * FROM accounts WHERE user_id = %s ORDER BY account_name", (user_id,))
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
        'transactions.html',
        transactions=transactions,
        accounts=accounts,
        categories=categories,
        total_income=total_income,
        total_expense=total_expense,
        net_flow=net_flow,
        filters={
            'start_date': start_date,
            'end_date': end_date,
            'category_id': category_id,
            'account_id': account_id,
            'txn_type': txn_type,
            'search': search,
            'min_amount': min_amount,
            'max_amount': max_amount
        },
        today_date=date.today().strftime("%Y-%m-%d")
    )


@transactions_bp.route('/transactions/add', methods=['POST'])
@login_required
def add_transaction():
    """
    Creates a new transaction using the MySQL Stored Procedure `sp_add_transaction`.
    Atomically performs insertion, validation, and balance update (via trigger).
    """
    user_id = session['user_id']
    account_id = request.form.get('account_id')
    category_id = request.form.get('category_id')
    amount_str = request.form.get('amount', '').strip()
    txn_type = request.form.get('txn_type', 'expense').strip()
    txn_date_str = request.form.get('txn_date', '').strip()
    description = request.form.get('description', '').strip()

    # Form validation
    if not account_id or not category_id or not amount_str or not txn_date_str:
        flash("Please fill in all required fields.", "danger")
        return redirect(request.referrer or url_for('transactions.list_transactions'))

    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(request.referrer or url_for('transactions.list_transactions'))
    except Exception:
        flash("Invalid amount entered.", "danger")
        return redirect(request.referrer or url_for('transactions.list_transactions'))

    try:
        # Call MySQL Stored Procedure sp_add_transaction
        # Signature: (p_user_id, p_account_id, p_category_id, p_amount, p_txn_type, p_txn_date, p_description, OUT p_txn_id, OUT p_status_code, OUT p_status_msg)
        db = get_db()
        cursor = db.cursor()

        args = [
            int(user_id),
            int(account_id),
            int(category_id),
            float(amount),
            txn_type,
            txn_date_str,
            description,
            0,   # OUT: p_txn_id
            0,   # OUT: p_status_code
            ''   # OUT: p_status_msg
        ]

        result = cursor.callproc('sp_add_transaction', args)
        db.commit()
        cursor.close()

        status_code = result[8]
        status_msg = result[9]

        if status_code == 0:
            flash(f"Transaction recorded successfully! (Account balance automatically updated via trigger)", "success")
        else:
            flash(f"Failed to record transaction: {status_msg}", "danger")

    except Exception as e:
        flash(f"Database error executing stored procedure: {str(e)}", "danger")

    return redirect(request.referrer or url_for('transactions.list_transactions'))


@transactions_bp.route('/transactions/<int:txn_id>/edit', methods=['POST'])
@login_required
def edit_transaction(txn_id):
    """
    Updates an existing transaction.
    The database trigger `trg_after_transaction_update` automatically reverses the OLD
    balance effect and applies the NEW balance effect across accounts.
    """
    user_id = session['user_id']
    account_id = request.form.get('account_id')
    category_id = request.form.get('category_id')
    amount_str = request.form.get('amount', '').strip()
    txn_type = request.form.get('txn_type', 'expense').strip()
    txn_date_str = request.form.get('txn_date', '').strip()
    description = request.form.get('description', '').strip()

    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(url_for('transactions.list_transactions'))

        query_db(
            """
            UPDATE transactions
            SET account_id = %s,
                category_id = %s,
                amount = %s,
                txn_type = %s,
                txn_date = %s,
                description = %s
            WHERE transaction_id = %s AND user_id = %s
            """,
            (account_id, category_id, amount, txn_type, txn_date_str, description, txn_id, user_id),
            commit=True
        )

        flash("Transaction updated successfully! Account balance resynchronized.", "success")
    except Exception as e:
        flash(f"Error updating transaction: {str(e)}", "danger")

    return redirect(url_for('transactions.list_transactions'))


@transactions_bp.route('/transactions/<int:txn_id>/delete', methods=['POST'])
@login_required
def delete_transaction(txn_id):
    """
    Deletes a transaction.
    The database trigger `trg_after_transaction_delete` automatically restores the balance.
    """
    user_id = session['user_id']
    try:
        query_db(
            "DELETE FROM transactions WHERE transaction_id = %s AND user_id = %s",
            (txn_id, user_id),
            commit=True
        )
        flash("Transaction deleted. Account balance restored via trigger.", "info")
    except Exception as e:
        flash(f"Error deleting transaction: {str(e)}", "danger")

    return redirect(request.referrer or url_for('transactions.list_transactions'))
