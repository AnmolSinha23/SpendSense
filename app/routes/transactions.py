"""
SpendSense - Transactions Management Route
Handles transaction creation (via MySQL Stored Procedure `sp_add_transaction`),
dynamic search/filtering, editing, and deletion.
Live account balances are automatically updated via MySQL database triggers.
"""

import io
import csv
import re
import calendar
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
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
        db = get_db()
        cursor = db.cursor()

        try:
            # Call MySQL Stored Procedure sp_add_transaction
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
            status_code = result[8]
            status_msg = result[9]
            cursor.close()

            if status_code == 0:
                flash(f"Transaction recorded successfully! (Account balance automatically updated via trigger)", "success")
            else:
                flash(f"Failed to record transaction: {status_msg}", "danger")
        except Exception:
            # Fallback for cloud database engines (like TiDB) where stored procedures are not supported
            cursor.execute(
                "INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, account_id, category_id, amount, txn_type, txn_date_str, description)
            )
            if txn_type == 'income':
                cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s", (amount, account_id))
            else:
                cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s", (amount, account_id))
            db.commit()
            cursor.close()
            flash("Transaction recorded successfully!", "success")

    except Exception as e:
        flash(f"Database error recording transaction: {str(e)}", "danger")

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


@transactions_bp.route('/transactions/sample-csv')
@login_required
def download_sample_csv():
    """
    Generates and downloads a pre-formatted sample CSV template for bulk transaction import.
    """
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Date', 'Type', 'Category', 'Account', 'Amount', 'Description'])
    writer.writerow(['2026-10-01', 'expense', 'Groceries & Provisions', 'Main Bank Account', '1450.00', 'Supermarket grocery run'])
    writer.writerow(['2026-10-02', 'expense', 'Dining Out & Food Delivery', 'Cash Wallet', '420.00', 'Lunch with friends'])
    writer.writerow(['2026-10-05', 'income', 'Salary', 'Main Bank Account', '75000.00', 'Monthly salary credit'])
    writer.writerow(['2026-10-06', 'expense', 'Utilities & Bills', 'Main Bank Account', '1200.00', 'Broadband internet bill'])
    writer.writerow(['2026-10-08', 'expense', 'Transportation & Fuel', 'Cash Wallet', '650.00', 'Petrol fill-up'])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=SpendSense_Sample_Template.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output


def clean_bank_remark(remark):
    """
    Intelligently extracts merchant or receiver names from complex bank UPI & NEFT narrations.
    e.g. 'UPI/245983127701/CR/NITIN /BKID/955584317/Paymen' -> 'NITIN (UPI)'
    """
    if not remark:
        return "Transaction"
    remark = str(remark).strip()
    if remark.startswith("UPI/"):
        parts = remark.split("/")
        if len(parts) >= 4:
            name = parts[3].strip()
            note = parts[6].strip() if len(parts) > 6 else (parts[-1].strip() if len(parts) > 4 else "")
            if note and note not in ("NO REM", "Paid v", "Paymen", "Sent u", "UPI", "UPIInt"):
                return f"{name} ({note})"
            return f"{name} (UPI)"
    if "SBInt" in remark:
        return "Bank Savings Interest"
    if "SMSChrgs" in remark:
        return "Bank SMS Charges"
    if remark.startswith("CWDR"):
        return "ATM Cash Withdrawal"
    if remark.startswith("NEFT"):
        parts = remark.split("/")
        if len(parts) >= 4:
            return f"NEFT: {parts[3].strip()}"
        return remark
    return remark


def infer_category(remark, txn_type):
    """
    Auto-categorizes transactions into standard 3NF categories based on merchant and narration keywords.
    """
    low = (remark or '').lower()
    if txn_type == 'income':
        if any(k in low for k in ['salary', 'salry', 'payroll', 'stipend']):
            return 'Salary'
        if any(k in low for k in ['sbint', 'interest', 'dividend', 'mutual', 'profit', 'stock', 'invest']):
            return 'Investments & Dividends'
        if any(k in low for k in ['cashback', 'bhimca', 'reward', 'gift', 'grant']):
            return 'Gifts & Grants'
        return 'Other Income'
    else:
        if any(k in low for k in ['swiggy', 'zomato', 'subway', 'kfc', 'mcdonald', 'domino', 'pizza', 'burger', 'cafe', 'bistro', 'restaurant', 'barbeque', 'food', 'hotel', 'dining', 'culinary', 'dinner', 'lunch']):
            return 'Dining Out & Food Delivery'
        if any(k in low for k in ['blinkit', 'blinki', 'grofer', 'dmart', 'nature basket', 'zepto', 'bigbasket', 'grocery', 'fruits', 'milk', 'dairy', 'provisions', 'supermarket']):
            return 'Groceries & Provisions'
        if any(k in low for k in ['amazon', 'flipkart', 'flipka', 'myntra', 'meesho', 'ajio', 'shopping', 'apparel', 'cloth', 'zara', 'h&m']):
            return 'Shopping & Apparel'
        if any(k in low for k in ['rapido', 'uber', 'ola', 'redbus', 'irctc', 'train', 'flight', 'petrol', 'diesel', 'fuel', 'hpcl', 'iocl', 'bpcl', 'fastag', 'cab', 'auto', 'metro', 'fare']):
            return 'Transportation & Fuel'
        if any(k in low for k in ['bill', 'electricity', 'broadband', 'airtel', 'jio', 'vi', 'vodafone', 'tata power', 'piped gas', 'water', 'recharge', 'postpaid', 'smschrg', 'airp']):
            return 'Utilities & Bills'
        if any(k in low for k in ['netflix', 'spotify', 'prime', 'hotstar', 'cinema', 'movie', 'imax', 'bookmyshow', 'theatre', 'game', 'playstore']):
            return 'Entertainment & Subscriptions'
        if any(k in low for k in ['pharmacy', 'apollo', 'medplus', 'hospital', 'doctor', 'clinic', 'medicine', 'health', 'lab']):
            return 'Healthcare & Pharmacy'
        if any(k in low for k in ['rent', 'house rent', 'flat', 'owner', 'maintenance', 'housing', 'hostel']):
            return 'Rent & Housing'
        if any(k in low for k in ['iiit', 'college', 'school', 'tuition', 'fee', 'exam', 'book', 'university', 'institute', 'course']):
            return 'Education & Books'
        if any(k in low for k in ['paytmqr', 'bharatpe', 'paytm']):
            return 'Shopping & Apparel'
        return None


@transactions_bp.route('/transactions/import-csv', methods=['POST'])
@login_required
def import_csv():
    """
    Parses both standard SpendSense templates and Indian bank statement CSV exports
    (Bank of India, SBI, HDFC, ICICI, etc.) with preambles, Debit/Credit columns, and UPI narrations.
    """
    user_id = session['user_id']
    file = request.files.get('csv_file')

    if not file or not file.filename:
        flash("Please select a CSV file to upload.", "warning")
        return redirect(url_for('transactions.list_transactions'))

    if not file.filename.lower().endswith('.csv'):
        flash("Invalid file format. Please upload a .csv file.", "danger")
        return redirect(url_for('transactions.list_transactions'))

    try:
        content = file.stream.read().decode('utf-8-sig', errors='replace')
        csv_file = io.StringIO(content)
        reader = csv.reader(csv_file)

        rows = list(reader)
        if not rows or len(rows) < 2:
            flash("The uploaded CSV file is empty or contains no data rows.", "warning")
            return redirect(url_for('transactions.list_transactions'))

        # 1. Preamble scanning (Detect Account Number / Bank Name from header metadata)
        detected_account_name = None
        for r in rows[:20]:
            line_str = " ".join(r)
            acc_match = re.search(r"Account Number\s*:\s*([A-Za-z0-9]+)", line_str, re.IGNORECASE)
            if acc_match:
                acc_num = acc_match.group(1).strip()
                last4 = acc_num[-4:] if len(acc_num) >= 4 else acc_num
                if "BKID" in line_str or any("BKID" in c for c in r):
                    detected_account_name = f"Bank of India (..{last4})"
                else:
                    detected_account_name = f"Bank Account (..{last4})"
                break

        # 2. Dynamic Table Header Finder (Skips bank preamble / metadata rows)
        header_row_idx = -1
        for idx, r in enumerate(rows):
            lower_cols = [c.strip().lower().replace('_', ' ').replace('-', ' ') for c in r]
            has_date = any('date' in c for c in lower_cols)
            has_amount_or_money = any(
                k in c for c in lower_cols for k in ['amount', 'debit', 'credit', 'withdrawal', 'deposit', 'dr', 'cr', 'val', 'balance']
            )
            if has_date and has_amount_or_money:
                header_row_idx = idx
                break

        if header_row_idx == -1:
            header_row_idx = 0

        header = [col.strip().lower().replace('_', ' ').replace('-', ' ') for col in rows[header_row_idx]]

        def find_col_idx(aliases):
            for alias in aliases:
                for idx, h in enumerate(header):
                    if alias == h or alias in h:
                        return idx
            return -1

        date_idx = find_col_idx(['date', 'txn date', 'txn. date', 'value date', 'time', 'timestamp'])
        desc_idx = find_col_idx(['remarks', 'description', 'particulars', 'narration', 'desc', 'note', 'memo', 'title', 'detail'])
        debit_idx = find_col_idx(['debit', 'withdrawal', 'dr', 'dr amt', 'debit amount'])
        credit_idx = find_col_idx(['credit', 'deposit', 'cr', 'cr amt', 'credit amount'])
        amount_idx = find_col_idx(['amount', 'total', 'amt', 'value', 'price', 'transaction amount'])
        type_idx = find_col_idx(['type', 'txn type', 'income/expense', 'transaction type', 'cr/dr'])
        cat_idx = find_col_idx(['category', 'cat', 'tag'])
        acc_idx = find_col_idx(['account', 'acc', 'wallet', 'bank', 'payment method'])

        if amount_idx == -1 and debit_idx == -1 and credit_idx == -1:
            flash("Could not find Amount or Debit/Credit columns in the CSV. Please check the file.", "danger")
            return redirect(url_for('transactions.list_transactions'))

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Pre-fetch existing user accounts
        cursor.execute("SELECT account_id, account_name FROM accounts WHERE user_id = %s", (user_id,))
        accounts = cursor.fetchall()
        acc_map = {a['account_name'].strip().lower(): a['account_id'] for a in accounts}

        # If a specific bank account was detected from preamble (e.g. Bank of India ..12725)
        if detected_account_name:
            if detected_account_name.lower() not in acc_map:
                cursor.execute(
                    "INSERT INTO accounts (user_id, account_name, account_type, balance) VALUES (%s, %s, 'Bank', 0.00)",
                    (user_id, detected_account_name)
                )
                db.commit()
                default_acc_id = cursor.lastrowid
                acc_map[detected_account_name.lower()] = default_acc_id
            else:
                default_acc_id = acc_map[detected_account_name.lower()]
        elif accounts:
            default_acc_id = accounts[0]['account_id']
        else:
            cursor.execute(
                "INSERT INTO accounts (user_id, account_name, account_type, balance) VALUES (%s, 'Main Bank Account', 'Bank', 0.00)",
                (user_id,)
            )
            db.commit()
            default_acc_id = cursor.lastrowid
            acc_map['main bank account'] = default_acc_id

        # Pre-fetch categories
        cursor.execute(
            "SELECT category_id, category_name, category_type FROM categories WHERE user_id IS NULL OR user_id = %s",
            (user_id,)
        )
        cats = cursor.fetchall()
        cat_map = {c['category_name'].strip().lower(): c['category_id'] for c in cats}
        default_expense_cat_id = next((c['category_id'] for c in cats if c['category_type'] == 'expense'), None)
        default_income_cat_id = next((c['category_id'] for c in cats if c['category_type'] == 'income'), None)

        def parse_date(date_str):
            if not date_str:
                return date.today().strftime('%Y-%m-%d')
            clean = date_str.strip().split('T')[0].split(' ')[0]
            formats = ['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d', '%b %d, %Y', '%d %b %Y']
            for fmt in formats:
                try:
                    return datetime.strptime(clean, fmt).strftime('%Y-%m-%d')
                except ValueError:
                    pass
            return date.today().strftime('%Y-%m-%d')

        def clean_num(val_str):
            cleaned = str(val_str).replace('₹', '').replace('$', '').replace('€', '').replace(',', '').strip()
            return Decimal(cleaned)

        success_count = 0
        skipped_count = 0
        net_balance_deltas = {}

        for row in rows[header_row_idx + 1:]:
            if not any(row):
                continue

            # Skip footer notes (e.g. "Note : Any discrepancy...")
            if date_idx == -1 or date_idx >= len(row) or not row[date_idx].strip():
                continue

            date_raw = row[date_idx].strip()
            if not re.search(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", date_raw):
                continue

            try:
                amount = None
                txn_type = None

                # 1. Check separate Debit / Credit columns first (standard Bank Statements)
                if debit_idx != -1 or credit_idx != -1:
                    d_val = row[debit_idx].strip() if debit_idx != -1 and debit_idx < len(row) else ''
                    c_val = row[credit_idx].strip() if credit_idx != -1 and credit_idx < len(row) else ''

                    if d_val:
                        try:
                            amt = clean_num(d_val)
                            if amt > 0:
                                amount = amt
                                txn_type = 'expense'
                        except Exception:
                            pass

                    if c_val and amount is None:
                        try:
                            amt = clean_num(c_val)
                            if amt > 0:
                                amount = amt
                                txn_type = 'income'
                        except Exception:
                            pass

                # 2. Check single Amount column
                if amount is None and amount_idx != -1 and amount_idx < len(row):
                    a_val = row[amount_idx].strip()
                    try:
                        amt = clean_num(a_val)
                        amount = abs(amt)
                        if type_idx != -1 and type_idx < len(row):
                            t_str = row[type_idx].lower()
                            txn_type = 'income' if any(k in t_str for k in ['inc', 'cr', 'credit', 'deposit']) else 'expense'
                        else:
                            txn_type = 'expense' if amt < 0 else 'expense'
                    except Exception:
                        pass

                if amount is None or amount <= 0:
                    skipped_count += 1
                    continue

                txn_date = parse_date(date_raw)

                # Raw remark and clean description
                raw_desc = row[desc_idx].strip() if desc_idx != -1 and desc_idx < len(row) else ''
                clean_desc = clean_bank_remark(raw_desc) if raw_desc else 'Transaction'

                # Account resolution
                acc_name_raw = row[acc_idx].strip() if acc_idx != -1 and acc_idx < len(row) else ''
                target_acc_id = acc_map.get(acc_name_raw.lower())
                if not target_acc_id:
                    if acc_name_raw:
                        cursor.execute(
                            "INSERT INTO accounts (user_id, account_name, account_type, balance) VALUES (%s, %s, 'Other', 0.00)",
                            (user_id, acc_name_raw)
                        )
                        target_acc_id = cursor.lastrowid
                        acc_map[acc_name_raw.lower()] = target_acc_id
                    else:
                        target_acc_id = default_acc_id

                # Category resolution (Smart inference from remark if category column is absent or empty)
                cat_name_raw = row[cat_idx].strip() if cat_idx != -1 and cat_idx < len(row) else ''
                if not cat_name_raw and raw_desc:
                    cat_name_raw = infer_category(raw_desc, txn_type) or ''

                target_cat_id = cat_map.get(cat_name_raw.lower()) if cat_name_raw else None
                if not target_cat_id:
                    if cat_name_raw:
                        cursor.execute(
                            "INSERT INTO categories (user_id, category_name, category_type, icon) VALUES (%s, %s, %s, 'bi-tag')",
                            (user_id, cat_name_raw, txn_type)
                        )
                        target_cat_id = cursor.lastrowid
                        cat_map[cat_name_raw.lower()] = target_cat_id
                    else:
                        target_cat_id = default_income_cat_id if txn_type == 'income' else default_expense_cat_id

                # Insert transaction record
                cursor.execute(
                    "INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, target_acc_id, target_cat_id, float(amount), txn_type, txn_date, clean_desc)
                )

                # Record net delta for account balance
                delta = amount if txn_type == 'income' else -amount
                net_balance_deltas[target_acc_id] = net_balance_deltas.get(target_acc_id, Decimal('0.00')) + delta

                success_count += 1

            except Exception:
                skipped_count += 1
                continue

        # Batch update account balances efficiently
        for acc_id, net_delta in net_balance_deltas.items():
            cursor.execute(
                "UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                (float(net_delta), acc_id)
            )

        db.commit()
        cursor.close()

        if success_count > 0:
            msg = f"Successfully imported {success_count} transactions from statement!"
            if detected_account_name:
                msg += f" (Linked to {detected_account_name})"
            if skipped_count > 0:
                msg += f" [{skipped_count} header/footer rows skipped]"
            flash(msg, "success")
        else:
            flash("No valid transactions found in the uploaded file.", "warning")

    except Exception as e:
        flash(f"Error parsing CSV statement: {str(e)}", "danger")

    return redirect(url_for('transactions.list_transactions'))
