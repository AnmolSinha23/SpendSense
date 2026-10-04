# SpendSense - Personal & Group Expenditure Tracking System

**SpendSense** is a comprehensive, production-grade expenditure tracking and budgeting system built for a College DBMS (Database Management Systems) semester course. It demonstrates advanced relational database principles using **raw SQL** (strictly no ORMs like SQLAlchemy) with **MySQL 8.0+**, a **Python Flask** backend, **Bootstrap 5** frontend, and **Chart.js** data visualizations.

---

## 🚀 Key Features

1. **User Authentication & Profiles**: Session-based login and registration with secure password hashing (`werkzeug.security` scrypt).
2. **Multi-Account Management**: Add, inspect, edit, and delete financial accounts (Cash, Bank, Savings, Credit Card, UPI, Wallets) with **real-time live balance synchronization**.
3. **Transaction Ledger**: Record, edit, delete, and inspect income and expense transactions.
4. **Trigger-Automated Balances**: Every transaction mutation automatically adjusts the corresponding account's balance via **database-level MySQL triggers**.
5. **Atomic Stored Procedures**: Creating transactions runs via `sp_add_transaction`, enforcing input validation, foreign key integrity, and ACID transaction boundaries.
6. **Default & Custom Categories**: Shared global system categories plus personalized user-defined categories.
7. **Monthly Budgeting & Threshold Alerts**: Set monthly budget ceilings per category, with color-coded warnings (<80% on track, 80–100% warning, >100% exceeded).
8. **Interactive Visual Reports**: Category spending breakdown (Doughnut Chart) and 6-month Income vs. Expense trend (Bar Chart) powered by **MySQL analytical VIEWs**.
9. **Multi-Criteria Search & Filter**: Filter transactions by date range, category, account, type, amount, or keyword.
10. **CSV Export**: One-click transaction ledger export formatted for spreadsheet analysis.

---

## 🛠 Tech Stack

| Tier | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | Python 3.12 + Flask | Web application routing, session auth, validation |
| **Database** | MySQL 8.0+ | Relational schema, 3NF tables, triggers, procedures, views |
| **DB Driver** | `mysql-connector-python` | Raw SQL execution with parameterized queries (No ORM) |
| **Frontend** | HTML5 + Jinja2 + Bootstrap 5.3 | Responsive modern UI with clean aesthetic |
| **Data Viz** | Chart.js 4.4 | Client-side dynamic charts for financial reports |
| **Icons** | Bootstrap Icons 1.11 | Visual icons for accounts and transaction categories |

---

## 📐 Database Schema & 3NF Normalization

The database (`spendsense_db`) is normalized to **Third Normal Form (3NF)** to eliminate update, insertion, and deletion anomalies.

```
                    ┌──────────────┐
                    │    users     │
                    └──────┬───────┘
                           │ 1:N
        ┌──────────────────┼──────────────────┐
        │ 1:N              │ 1:N              │ 1:N
 ┌──────▼───────┐   ┌──────▼───────┐   ┌──────▼───────┐
 │   accounts   │   │  categories  │   │   budgets    │
 └──────┬───────┘   └──────┬───────┘   └──────────────┘
        │ 1:N              │ 1:N
        └──────────┬───────┘
                   │
            ┌──────▼───────┐
            │ transactions │
            └──────────────┘
```

### Normalization Breakdown:
- **1NF (First Normal Form)**:
  - Every column contains atomic (indivisible) values.
  - Every table has a Primary Key (`user_id`, `account_id`, `category_id`, `transaction_id`, `budget_id`).
  - No repeating groups or multivalued attributes.
- **2NF (Second Normal Form)**:
  - Satisfies 1NF.
  - All non-key attributes are fully functionally dependent on the entire Primary Key. (No partial dependencies exist since all primary keys are single-column surrogate keys).
- **3NF (Third Normal Form)**:
  - Satisfies 2NF.
  - No transitive dependencies ($X \rightarrow Y \rightarrow Z$).
  - Example: `transactions` does **not** store `account_name` or `category_name`. It stores strictly foreign keys `account_id` and `category_id`. Changes to an account name or category icon propagate without modifying historical transactions.

---

## 🎓 DBMS Concepts Mapping to Code

Use this table to navigate the codebase during your project viva/presentation:

| DBMS Concept | Implementation Location | Relational Explanation |
| :--- | :--- | :--- |
| **DDL & Constraints** | `sql/schema.sql` | `PRIMARY KEY`, `FOREIGN KEY ... ON DELETE CASCADE`, `CHECK (amount > 0)`, `UNIQUE (email)`, `NOT NULL`. |
| **Database Triggers** | `sql/triggers.sql` | `trg_after_transaction_insert`: Credits/debits account on transaction insert.<br>`trg_after_transaction_update`: Adjusts old and new accounts if amounts, types, or accounts change.<br>`trg_after_transaction_delete`: Reverses balance upon transaction removal. |
| **Stored Procedures** | `sql/procedures.sql` | `sp_add_transaction`: Validates ownership & inputs, executes inside `START TRANSACTION;` and `COMMIT;` with `DECLARE EXIT HANDLER FOR SQLEXCEPTION` rollback.<br>`sp_delete_transaction`: Authorizes user and deletes safely.<br>`sp_get_monthly_analytics`: Computes aggregates on the database engine. |
| **Database Views** | `sql/views.sql` | `view_monthly_category_summary`: Aggregates using `INNER JOIN`, `GROUP BY`, `SUM()`, `COUNT()`, `AVG()`.<br>`view_monthly_budget_status`: Matches budgets with spending using `LEFT JOIN` and derived subqueries.<br>`view_account_financial_summary`: Inflow and outflow totals per account. |
| **Transactions & ACID** | `sql/procedures.sql`, `app/routes/transactions.py` | Explicit `START TRANSACTION` / `COMMIT` / `ROLLBACK` guarantees atomicity across financial ledgers. |
| **Parameterized Queries** | `app/db.py`, `app/routes/*.py` | All queries use `%s` parameter binding to prevent SQL Injection attacks. |

---

## ⚡ Quick Setup & Installation

### Step 1: Clone or Navigate to the Project
```bash
cd "c:\Users\anmol\Documents\DBMS PROJECT"
```

### Step 2: Configure Environment (`.env`)
A `.env` file is created at the project root. Update the MySQL password to match your local installation:
```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=spendsense_db
SECRET_KEY=spendsense_secret_key_college_dbms_project_2026
FLASK_DEBUG=1
```

### Step 3: Initialize Database Schema, Triggers, Views & Seed Data
Run the automated initialization script:
```bash
python init_db.py
```
*Alternatively, you can open `sql/setup_database.sql` inside **MySQL Workbench** and execute the entire script.*

### Step 4: Run the Flask Application
```bash
python run.py
```
Open your web browser and visit: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔑 Demo Login Credentials

The seed script loads pre-configured demo users with realistic financial history spanning June–September 2026:

| User | Email | Password | Details |
| :--- | :--- | :--- | :--- |
| **Rahul Sharma** | `rahul@example.com` | `Password@123` | 5 accounts, 35+ transactions, active budgets |
| **Priya Patel** | `priya@example.com` | `Password@123` | Secondary user demonstrating multi-tenant isolation |

*(You can also click "Fill Demo" on the login page for instantaneous 1-click login!)*

---

## 🔍 End-to-End Walkthrough: "Add Transaction" Request

When the examiner asks: *"Explain what happens when a user records a transaction"*, explain this 6-step lifecycle:

```
[Browser Form]
      │ HTTP POST /transactions/add (amount, category, account, type, date)
      ▼
[Flask Route: app/routes/transactions.py]
      │ 1. Validates session['user_id'] (@login_required)
      │ 2. Validates amount > 0 and input fields
      │ 3. Invokes MySQL Stored Procedure: cursor.callproc('sp_add_transaction', [...])
      ▼
[MySQL Stored Procedure: sp_add_transaction]
      │ 1. Verifies account_id belongs to authenticated user
      │ 2. Verifies category exists
      │ 3. Executes START TRANSACTION;
      │ 4. Executes INSERT INTO transactions (...)
      ▼
[MySQL Trigger: trg_after_transaction_insert]
      │ Automatically fires synchronously inside the same ACID transaction:
      │   UPDATE accounts SET balance = balance - NEW.amount WHERE account_id = NEW.account_id;
      ▼
[MySQL Engine]
      │ If any check fails: Handler executes ROLLBACK;
      │ If successful: Executes COMMIT; and returns OUT p_txn_id, OUT p_status_code = 0
      ▼
[Flask Response]
      │ Flashes "Transaction recorded successfully! Balance updated."
      │ Redirects user back to Dashboard or Transactions list
```

---

## 📂 Project Structure

```
DBMS PROJECT/
├── sql/
│   ├── schema.sql              # 3NF DDL (Tables, Primary & Foreign Keys, Constraints)
│   ├── triggers.sql            # Triggers for automated balance sync (Insert/Update/Delete)
│   ├── procedures.sql          # Stored procedures (sp_add_transaction, sp_delete_transaction)
│   ├── views.sql               # Analytical views (Category summaries, Budget health, Accounts)
│   ├── seed.sql                # Realistic seed data (Users, Accounts, Transactions, Budgets)
│   └── setup_database.sql      # Consolidated master setup script
├── app/
│   ├── __init__.py             # Flask App Factory & Blueprint registration
│   ├── db.py                   # Raw SQL database connection & stored procedure runner
│   ├── routes/
│   │   ├── auth.py             # User signup, login, session management
│   │   ├── dashboard.py        # Dashboard metrics, recent txns, budget alerts
│   │   ├── accounts.py         # Accounts CRUD and live balances
│   │   ├── transactions.py     # Transactions CRUD, multi-criteria filter, SP integration
│   │   ├── categories.py       # Default vs. custom categories manager
│   │   ├── budgets.py          # Category budget ceilings and progress bars
│   │   └── reports.py          # Chart.js analytics & CSV export
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html           # Navbar, footer, flash alerts, quick modals
│   │   ├── dashboard.html      # Central dashboard
│   │   ├── accounts.html       # Accounts overview
│   │   ├── transactions.html   # Filterable transaction ledger
│   │   ├── categories.html     # Category settings
│   │   ├── budgets.html        # Budget planner
│   │   ├── reports.html        # Visual analytics
│   │   └── auth/               # Login & Register views
│   └── static/
│       ├── css/style.css       # Custom styling
│       └── js/reports.js       # Chart.js chart initializers
├── config.py                   # Application settings & environment loader
├── init_db.py                  # CLI Python database initialiser
├── run.py                      # Flask server entry point
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment variables
├── .gitignore                  # Git ignore rules
└── README.md                   # Comprehensive documentation & viva guide
```
