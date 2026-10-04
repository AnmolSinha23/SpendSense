# SpendSense — Expenditure & Budget Tracking System

**SpendSense** is a web-based expenditure tracking and budgeting system built by our team for our Database Management Systems (DBMS) semester project. 

The goal of this project was to build a clean, reliable financial tracking tool that handles both personal and shared expenses across multiple payment modes (UPI, Cash, Bank Accounts, Cards), while practicing low-level relational database design using **raw SQL** rather than relying on an ORM.

---

## Project Motivation & Engineering Decisions

As college students managing personal allowances, shared hostel/apartment expenses, and freelance gigs across UPI and bank accounts, we found that existing spreadsheet templates often get out of sync, while commercial apps hide the underlying data logic.

When planning our technical stack, our team made several deliberate engineering choices:

### 1. Raw SQL over an ORM (No SQLAlchemy)
Most modern Flask tutorials use SQLAlchemy or another ORM. We deliberately avoided ORMs and used `mysql-connector-python` with parameterized queries (`%s`). Since this project is for our DBMS course, we wanted full visibility and control over:
- Writing our own DDL with explicit relational constraints and cascading rules.
- Writing raw SQL `JOIN`s, `GROUP BY` clauses, and aggregate functions (`SUM`, `COUNT`, `AVG`).
- Managing explicit transaction boundaries (`START TRANSACTION`, `COMMIT`, `ROLLBACK`).
- Eliminating SQL injection risks through parameter binding without ORM abstraction.

### 2. Database-Enforced Balance Synchronization (Triggers)
A common flaw in basic CRUD apps is updating balances in application-level Python code (e.g., `account.balance -= amount`). If an external script, admin tool, or concurrent request mutates a transaction, the account balance immediately drifts out of sync. 

We moved balance synchronization directly into MySQL engine triggers:
- `trg_after_transaction_insert`: Automatically debits or credits the associated account.
- `trg_after_transaction_update`: Corrects the old account and adjusts the new account if amounts, transaction types, or accounts change.
- `trg_after_transaction_delete`: Reverses the financial impact when a transaction is removed.

### 3. Atomic Transactions via Stored Procedures
For adding transactions, we implemented `sp_add_transaction`. The procedure performs input checks (ensuring `amount > 0`, verifying account ownership, and validating categories), starts a database transaction, inserts the row, lets the trigger update the balance, and commits. If any step fails, an `SQLEXCEPTION` handler rolls back the transaction entirely, guaranteeing ACID compliance.

### 4. Normalized Category Modeling (Default vs. Custom)
We wanted users to have standard categories (Salary, Groceries, Rent, Utilities) out of the box while allowing them to create custom ones. Instead of creating two separate tables or duplicating default rows for every user, we designed `categories.user_id` as a nullable foreign key:
- Rows with `user_id IS NULL` are system defaults visible to everyone.
- Rows with `user_id = <current_user>` are custom categories visible only to that user.

---

## Key Features

- **Authentication**: Session-based login and signup with password hashing using `werkzeug.security` (scrypt).
- **Accounts Hub**: Supports Bank accounts, Cash, Credit Cards, and UPI wallets with live balances updated by triggers.
- **Transaction Ledger**: Add, edit, delete, and inspect transactions with filtering across dates, accounts, categories, types, and amounts.
- **Monthly Budgets & Alerts**: Set category budget limits per month. The system calculates spending percentages and flags:
  - 🟢 **On Track** (<80% spent)
  - 🟡 **Warning** (80%–100% spent)
  - 🔴 **Exceeded** (>100% spent)
- **Analytical Reports & Charts**: Visual category breakdown (Doughnut chart) and 6-month Income vs. Expense trend (Bar chart) rendered with Chart.js from a database VIEW.
- **CSV Ledger Export**: Download transactions directly as a CSV file.

---

## Database Architecture & 3NF Normalization

We designed the database (`spendsense_db`) to strictly follow **Third Normal Form (3NF)**:

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

### Normalization Steps We Followed:

1. **1NF (First Normal Form)**:
   - All columns hold atomic values (e.g., amounts are single decimal values, dates are standard date types).
   - Every table has a dedicated single-column primary key (`user_id`, `account_id`, `category_id`, `transaction_id`, `budget_id`).
   - No repeating groups or comma-separated lists in any field.

2. **2NF (Second Normal Form)**:
   - The schema satisfies 1NF.
   - All primary keys are single-column keys, which completely rules out partial functional dependencies. Every non-key column depends on the whole primary key.

3. **3NF (Third Normal Form)**:
   - The schema satisfies 2NF.
   - We eliminated transitive dependencies ($X \rightarrow Y \rightarrow Z$).
   - For example, `transactions` only stores `account_id` and `category_id` foreign keys. It does **not** store `account_name`, `account_type`, or `category_name`. If a user renames an account, existing transactions are unaffected and there is zero data duplication.

---

## DBMS Concepts Implemented in Our Code

| Concept | File Location | How We Implemented It |
| :--- | :--- | :--- |
| **DDL & Constraints** | [`sql/schema.sql`](sql/schema.sql) | Table creation with `PRIMARY KEY`, `FOREIGN KEY ... ON DELETE CASCADE`, `CHECK (amount > 0)`, `CHECK (budget_amount > 0)`, `UNIQUE`, and `NOT NULL`. |
| **Database Triggers** | [`sql/triggers.sql`](sql/triggers.sql) | `trg_after_transaction_insert`, `trg_after_transaction_update`, and `trg_after_transaction_delete` keep `accounts.balance` in sync whenever rows change in `transactions`. |
| **Stored Procedures** | [`sql/procedures.sql`](sql/procedures.sql) | `sp_add_transaction` validates inputs and runs within `START TRANSACTION` / `COMMIT` / `ROLLBACK` blocks. `sp_delete_transaction` verifies ownership before deletion. |
| **Database Views** | [`sql/views.sql`](sql/views.sql) | `view_monthly_category_summary` aggregates spending per category/month using `INNER JOIN` and `GROUP BY`. `view_monthly_budget_status` joins budgets with a derived spending subquery to compute used percentages. |
| **ACID Transactions** | [`sql/procedures.sql`](sql/procedures.sql), [`app/db.py`](app/db.py) | Procedures and database connection helpers handle commit/rollback explicitly to keep accounts consistent. |
| **SQL Injection Prevention** | [`app/db.py`](app/db.py), [`app/routes/`](app/routes/) | All queries strictly use `%s` parameter substitution with tuples/lists. No f-string SQL interpolation. |

---

## How an "Add Transaction" Request Works End-to-End

To ensure our team understood the full lifecycle of data moving between the browser and MySQL, we mapped the flow of an "Add Transaction" request:

```
[Browser Form]
       │ 1. User submits transaction form (Amount, Category, Account, Type, Date, Note)
       ▼
[Flask Route: app/routes/transactions.py]
       │ 2. Validates session authentication via @login_required
       │ 3. Validates required fields and checks amount > 0
       │ 4. Calls MySQL stored procedure: cursor.callproc('sp_add_transaction', [...])
       ▼
[MySQL Stored Procedure: sp_add_transaction]
       │ 5. Validates account ownership (user_id matches account owner)
       │ 6. Validates category exists and is accessible
       │ 7. Starts transaction: START TRANSACTION;
       │ 8. Executes: INSERT INTO transactions (...) VALUES (...);
       ▼
[MySQL Trigger: trg_after_transaction_insert]
       │ 9. Fires automatically inside the open transaction:
       │    UPDATE accounts SET balance = balance - NEW.amount WHERE account_id = NEW.account_id;
       ▼
[MySQL Engine Execution]
       │ 10. If error occurs: Handler executes ROLLBACK;
       │     If successful: Executes COMMIT; and returns OUT status_code = 0
       ▼
[Flask Route Response]
       │ 11. Reads procedure OUT parameters
       │ 12. Flashes success message to user session
       │ 13. Redirects browser back to Dashboard / Ledger with updated live balances
```

---

## Codebase Organization

We organized the codebase into modular components rather than keeping all logic in a single file:

```
DBMS PROJECT/
├── sql/
│   ├── schema.sql              # DDL schema definition normalized to 3NF
│   ├── triggers.sql            # Balance synchronization triggers
│   ├── procedures.sql          # Stored procedures for transaction logic
│   ├── views.sql               # Relational views for reporting and budget monitoring
│   ├── seed.sql                # Seed data (2 users, 7 accounts, 16 categories, 40 txns)
│   └── setup_database.sql      # Consolidated master setup script
├── app/
│   ├── __init__.py             # Flask app factory, custom Jinja filters, blueprints
│   ├── db.py                   # Raw SQL database connection & stored procedure helpers
│   ├── routes/
│   │   ├── auth.py             # User signup, login, session management
│   │   ├── dashboard.py        # Summary metrics, live balances, budget alerts
│   │   ├── accounts.py         # Multi-account CRUD operations
│   │   ├── transactions.py     # Transaction ledger & multi-criteria filtering
│   │   ├── categories.py       # Default vs. custom category management
│   │   ├── budgets.py          # Category budget limits and warnings
│   │   └── reports.py          # Chart.js analytics & CSV export
│   ├── templates/              # Jinja2 templates styled with Bootstrap 5
│   │   ├── base.html           # Base layout, navbar, flash alerts, global quick modals
│   │   ├── dashboard.html      # Overview dashboard
│   │   ├── accounts.html       # Financial accounts list and management modals
│   │   ├── transactions.html   # Filterable transactions table
│   │   ├── categories.html     # Categories view
│   │   ├── budgets.html        # Budget planner with progress bars
│   │   ├── reports.html        # Doughnut and Bar charts
│   │   └── auth/               # Login & Register templates
│   └── static/
│       ├── css/style.css       # Custom styles
│       └── js/reports.js       # Chart.js initialization script
├── config.py                   # App configuration & .env loader
├── init_db.py                  # Python script to run setup_database.sql
├── run.py                      # Flask server entry point
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment configuration
├── .env                        # Local database credentials (ignored by Git)
├── .gitignore                  # Git ignore rules
└── README.md                   # Project documentation
```

---

## Local Setup & Installation

### 1. Prerequisites
- Python 3.10+
- MySQL Server 8.0+ running locally on port 3306

### 2. Configure Environment (`.env`)
Create or update `.env` in the root folder with your local MySQL credentials:
```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=spendsense_db
SECRET_KEY=spendsense_secret_key_college_dbms_project_2026
FLASK_DEBUG=1
```

### 3. Initialize Database & Seed Data
We wrote an automated initialization script that parses and runs [`sql/setup_database.sql`](sql/setup_database.sql):
```bash
python init_db.py
```
*(Alternatively, you can open `sql/setup_database.sql` in **MySQL Workbench** and execute it directly).*

### 4. Start the Application
```bash
python run.py
```
Open your browser and navigate to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## Seed Data for Demo

To test and demonstrate the system immediately, our seed script populates realistic data spanning June to September 2026:

| User | Email | Password | What It Demonstrates |
| :--- | :--- | :--- | :--- |
| **Rahul Sharma** | `rahul@example.com` | `Password@123` | 5 accounts (Bank, Savings, Cash, Card, UPI), 35+ transactions across categories, and active budgets showing On Track, Warning, and Exceeded states. |
| **Priya Patel** | `priya@example.com` | `Password@123` | Secondary user showing multi-user account and transaction isolation. |

*(There is also a **"Fill Demo"** button on the login screen for quick 1-click credential entry).*
