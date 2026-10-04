-- ============================================================================
-- PROJECT: SpendSense - Personal & Group Expenditure Tracking System
-- MODULE: Database Views for Analytical Reports & Dashboards
-- DBMS: MySQL 8.0+
--
-- DBMS VIVA CONCEPT EXPLANATION:
-- A VIEW is a virtual table defined by a saved SQL query.
-- Advantages in DBMS:
-- 1. Query Simplification: Hides complex multi-table JOINs, GROUP BYs, and aggregations
--    behind a clean virtual table interface.
-- 2. Security & Abstraction: Restricts direct access to underlying base tables,
--    exposing only computed and relevant columns.
-- 3. Consistency: Ensures all application reports, charts, and API endpoints
--    compute metrics using the exact same standard business logic.
-- ============================================================================

USE spendsense_db;

-- ----------------------------------------------------------------------------
-- VIEW 1: view_monthly_category_summary
-- Purpose:
--   Powers the category-wise expenditure and income reports (e.g., Pie/Doughnut charts).
-- Relational Concepts Used:
--   - INNER JOIN between transactions, categories, and users
--   - GROUP BY on user, year, month, and category
--   - Aggregate functions: SUM(), COUNT(), AVG(), MIN(), MAX()
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS view_monthly_category_summary;

CREATE VIEW view_monthly_category_summary AS
SELECT
    t.user_id,
    YEAR(t.txn_date) AS year,
    MONTH(t.txn_date) AS month,
    t.category_id,
    c.category_name,
    c.category_type,
    c.icon AS category_icon,
    SUM(t.amount) AS total_amount,
    COUNT(t.transaction_id) AS transaction_count,
    ROUND(AVG(t.amount), 2) AS avg_transaction_amount,
    MIN(t.amount) AS min_transaction_amount,
    MAX(t.amount) AS max_transaction_amount
FROM transactions t
INNER JOIN categories c ON t.category_id = c.category_id
INNER JOIN users u ON t.user_id = u.user_id
GROUP BY
    t.user_id,
    YEAR(t.txn_date),
    MONTH(t.txn_date),
    t.category_id,
    c.category_name,
    c.category_type,
    c.icon;


-- ----------------------------------------------------------------------------
-- VIEW 2: view_monthly_budget_status
-- Purpose:
--   Powers the Budget Health Monitor and Over-Budget Alert system.
-- Relational Concepts Used:
--   - LEFT OUTER JOIN to match budgets with aggregated actual spending
--   - Derived Table (Subquery) for pre-aggregating transaction amounts
--   - CASE expressions for dynamic status classification (ON_TRACK, WARNING, EXCEEDED)
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS view_monthly_budget_status;

CREATE VIEW view_monthly_budget_status AS
SELECT
    b.budget_id,
    b.user_id,
    b.month,
    b.year,
    b.category_id,
    c.category_name,
    c.icon AS category_icon,
    b.budget_amount,
    COALESCE(spent.total_spent, 0.00) AS actual_spent,
    ROUND(b.budget_amount - COALESCE(spent.total_spent, 0.00), 2) AS remaining_budget,
    ROUND(
        CASE
            WHEN b.budget_amount > 0 THEN (COALESCE(spent.total_spent, 0.00) / b.budget_amount) * 100
            ELSE 0.00
        END,
        1
    ) AS percentage_used,
    CASE
        WHEN COALESCE(spent.total_spent, 0.00) > b.budget_amount THEN 'EXCEEDED'
        WHEN COALESCE(spent.total_spent, 0.00) >= (b.budget_amount * 0.80) THEN 'WARNING'
        ELSE 'ON_TRACK'
    END AS budget_status
FROM budgets b
INNER JOIN categories c ON b.category_id = c.category_id
LEFT JOIN (
    SELECT
        user_id,
        category_id,
        YEAR(txn_date) AS txn_year,
        MONTH(txn_date) AS txn_month,
        SUM(amount) AS total_spent
    FROM transactions
    WHERE txn_type = 'expense'
    GROUP BY user_id, category_id, YEAR(txn_date), MONTH(txn_date)
) spent ON b.user_id = spent.user_id
       AND b.category_id = spent.category_id
       AND b.year = spent.txn_year
       AND b.month = spent.txn_month;


-- ----------------------------------------------------------------------------
-- VIEW 3: view_account_financial_summary
-- Purpose:
--   Powers the Accounts Overview dashboard with cumulative inflows & outflows.
-- Relational Concepts Used:
--   - LEFT JOIN from accounts to transactions
--   - Conditional Aggregation using CASE inside SUM()
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS view_account_financial_summary;

CREATE VIEW view_account_financial_summary AS
SELECT
    a.account_id,
    a.user_id,
    a.account_name,
    a.account_type,
    a.balance AS current_balance,
    COALESCE(SUM(CASE WHEN t.txn_type = 'income' THEN t.amount ELSE 0 END), 0.00) AS total_inflow,
    COALESCE(SUM(CASE WHEN t.txn_type = 'expense' THEN t.amount ELSE 0 END), 0.00) AS total_outflow,
    COUNT(t.transaction_id) AS total_transactions
FROM accounts a
LEFT JOIN transactions t ON a.account_id = t.account_id
GROUP BY
    a.account_id,
    a.user_id,
    a.account_name,
    a.account_type,
    a.balance;
