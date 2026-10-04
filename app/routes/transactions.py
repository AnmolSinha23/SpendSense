"""
SpendSense - Transactions Management Route
Handles transaction creation (via MySQL Stored Procedure `sp_add_transaction`),
dynamic search/filtering, editing, and deletion.
Live account balances are automatically updated via MySQL database triggers.
"""

import calendar
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db import query_db, get_db
from app.routes.auth import login_required

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/transactions')
@login_required
def list_transactions():
    """
    Renders filtered transaction list with multi-criteria search:
    - Smart Date Presets (This Month, Last 30 Days, This Quarter, This Year, Custom)
    - Category
    - Account
    - Transaction type (income / expense)
    - Amount range
    - Text search on description & category
    """
    user_id = session['user_id']

    # Filter parameters from request
    date_preset = request.args.get('date_preset', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    category_id = request.args.get('category_id', '').strip()
    account_id = request.args.get('account_id', '').strip()
    txn_type = request.args.get('txn_type', '').strip()
    search = request.args.get('search', '').strip()
    min_amount = request.args.get('min_amount', '').strip()
    max_amount = request.args.get('max_amount', '').strip()

    # Calculate smart date ranges if preset is selected
    today = date.today()
    if date_preset == 'this_month':
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        _, last_day = calendar.monthrange(today.year, today.month)
        end_date = date(today.year, today.month, last_day).strftime("%Y-%m-%d")
    elif date_preset == 'last_30_days':
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
    elif date_preset == 'this_quarter':
        quarter = (today.month - 1) // 3 + 1
        q_start_month = (quarter - 1) * 3 + 1
        q_end_month = q_start_month + 2
        _, last_day = calendar.monthrange(today.year, q_end_month)
        start_date = date(today.year, q_start_month, 1).strftime("%Y-%m-%d")
        end_date = date(today.year, q_end_month, last_day).strftime("%Y-%m-%d")
    elif date_preset == 'this_year':
        start_date = date(today.year, 1, 1).strftime("%Y-%m-%d")
        end_date = date(today.year, 12, 31).strftime("%Y-%m-%d")
    elif date_preset == 'all':
        start_date = ''
        end_date = ''

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

    # Compute active filter chips for dismissible UI
    active_filters = []
    if search:
        active_filters.append({'key': 'search', 'label': f'Search: "{search}"'})

    preset_labels = {
        'this_month': 'This Month',
        'last_30_days': 'Last 30 Days',
        'this_quarter': 'This Quarter',
        'this_year': 'This Year',
        'custom': f'{start_date} to {end_date}' if (start_date or end_date) else 'Custom Range'
    }
    if date_preset and date_preset in preset_labels:
        active_filters.append({'key': 'date_preset', 'label': f'Date: {preset_labels[date_preset]}'})
    elif start_date or end_date:
        active_filters.append({'key': 'date_range', 'label': f'Date: {start_date or "..."} to {end_date or "..."}'})

    if txn_type in ('income', 'expense'):
        active_filters.append({'key': 'txn_type', 'label': f'Type: {txn_type.capitalize()}'})

    if category_id:
        cat_match = next((c['category_name'] for c in categories if str(c['category_id']) == category_id), None)
        if cat_match:
            active_filters.append({'key': 'category_id', 'label': f'Category: {cat_match}'})

    if account_id:
        acc_match = next((a['account_name'] for a in accounts if str(a['account_id']) == account_id), None)
        if acc_match:
            active_filters.append({'key': 'account_id', 'label': f'Account: {acc_match}'})

    if min_amount:
        active_filters.append({'key': 'min_amount', 'label': f'Min: ₹{min_amount}'})

    if max_amount:
        active_filters.append({'key': 'max_amount', 'label': f'Max: ₹{max_amount}'})

    return render_template(
        'transactions.html',
        transactions=transactions,
        accounts=accounts,
        categories=categories,
        total_income=total_income,
        total_expense=total_expense,
        net_flow=net_flow,
        active_filters=active_filters,
        filters={
            'date_preset': date_preset,
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
