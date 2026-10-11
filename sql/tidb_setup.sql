-- ============================================================================
-- SpendSense - TiDB Cloud & Cloud MySQL Setup Script
-- Compatible with all cloud database engines (No DELIMITER, No Triggers required)
-- Contains: Clean 3NF Schema + Views + Demo User (Rahul Sharma / Password@123)
-- ============================================================================

CREATE DATABASE IF NOT EXISTS spendsense_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE spendsense_db;

-- ----------------------------------------------------------------------------
-- 1. DROP EXISTING TABLES AND VIEWS SAFELY
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS view_monthly_budget_status;
DROP VIEW IF EXISTS view_account_financial_summary;
DROP TABLE IF EXISTS budgets;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS users;

-- ----------------------------------------------------------------------------
-- 2. DDL SCHEMA (3NF NORMALIZED)
-- ----------------------------------------------------------------------------

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NULL,
    google_sub VARCHAR(255) UNIQUE DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_user_email_not_empty CHECK (CHAR_LENGTH(TRIM(email)) > 0),
    CONSTRAINT chk_user_name_not_empty CHECK (CHAR_LENGTH(TRIM(name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE accounts (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    account_type ENUM('Cash', 'Bank', 'Credit Card', 'Debit Card', 'UPI', 'Savings', 'Other') NOT NULL DEFAULT 'Bank',
    balance DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT chk_account_name_not_empty CHECK (CHAR_LENGTH(TRIM(account_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    category_name VARCHAR(100) NOT NULL,
    category_type ENUM('income', 'expense') NOT NULL,
    icon VARCHAR(50) DEFAULT 'bi-tag',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT chk_category_name_not_empty CHECK (CHAR_LENGTH(TRIM(category_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    account_id INT NOT NULL,
    category_id INT NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    txn_type ENUM('income', 'expense') NOT NULL,
    txn_date DATE NOT NULL,
    description VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT,
    CONSTRAINT chk_positive_amount CHECK (amount > 0)
) ENGINE=InnoDB;

CREATE INDEX idx_transactions_user_date ON transactions(user_id, txn_date DESC);
CREATE INDEX idx_transactions_account ON transactions(account_id);
CREATE INDEX idx_transactions_category ON transactions(category_id);

CREATE TABLE budgets (
    budget_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category_id INT NOT NULL,
    budget_amount DECIMAL(12, 2) NOT NULL,
    month INT NOT NULL,
    year INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE,
    CONSTRAINT chk_budget_amount_positive CHECK (budget_amount > 0),
    CONSTRAINT chk_valid_month CHECK (month BETWEEN 1 AND 12),
    CONSTRAINT chk_valid_year CHECK (year >= 2000),
    CONSTRAINT uq_user_category_month_year UNIQUE (user_id, category_id, month, year)
) ENGINE=InnoDB;

CREATE INDEX idx_budgets_user_period ON budgets(user_id, year, month);

-- ----------------------------------------------------------------------------
-- 3. ANALYTICAL VIEWS
-- ----------------------------------------------------------------------------

CREATE VIEW view_monthly_budget_status AS
SELECT
    b.budget_id,
    b.user_id,
    b.category_id,
    c.category_name,
    c.icon,
    b.month,
    b.year,
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

-- ----------------------------------------------------------------------------
-- 4. SEED DATA (USERS, DEMO EVALUATOR, ACCOUNTS, TRANSACTIONS, BUDGETS)
-- ----------------------------------------------------------------------------

-- Seed Users: Anmol (Evaluator Demo Account: Password@123) & Priya Patel
INSERT INTO users (user_id, name, email, password_hash, created_at) VALUES
(1, 'Anmol', 'anmol@example.com', 'scrypt:32768:8:1$lYUQeHrOYZMDGVo2$50dd391a132f80708aabcbf5e7caceccb5c31cbedbab09c5856aef7b949acf66fbe52bf7dc901648b0a7b66c3076778d065dda575c5a2b0fc81892c95ea831dc', '2026-06-01 10:00:00'),
(2, 'Priya Patel', 'priya@example.com', 'scrypt:32768:8:1$lYUQeHrOYZMDGVo2$50dd391a132f80708aabcbf5e7caceccb5c31cbedbab09c5856aef7b949acf66fbe52bf7dc901648b0a7b66c3076778d065dda575c5a2b0fc81892c95ea831dc', '2026-07-01 11:30:00');

-- Seed Accounts with pre-calculated balances reflecting all transactions
INSERT INTO accounts (account_id, user_id, account_name, account_type, balance, created_at) VALUES
(1, 1, 'HDFC Salary Account', 'Bank', 286500.00, '2026-06-01 10:05:00'),
(2, 1, 'SBI Savings', 'Savings', 9800.00, '2026-06-01 10:10:00'),
(3, 1, 'ICICI Amazon Pay Card', 'Credit Card', -42749.00, '2026-06-01 10:15:00'),
(4, 1, 'Cash Wallet', 'Cash', -2150.00, '2026-06-01 10:20:00'),
(5, 1, 'Google Pay UPI', 'UPI', -48900.00, '2026-06-01 10:25:00'),
(6, 2, 'Kotak Mahindra Bank', 'Bank', 52000.00, '2026-07-01 11:35:00'),
(7, 2, 'Paytm Wallet', 'UPI', -7000.00, '2026-07-01 11:40:00');

-- Seed Categories (Global Defaults + Rahul's Custom Categories)
INSERT INTO categories (category_id, user_id, category_name, category_type, icon) VALUES
(1, NULL, 'Salary', 'income', 'bi-cash-stack'),
(2, NULL, 'Freelance & Consulting', 'income', 'bi-laptop'),
(3, NULL, 'Investments & Dividends', 'income', 'bi-graph-up'),
(4, NULL, 'Gifts & Grants', 'income', 'bi-gift'),
(5, NULL, 'Other Income', 'income', 'bi-wallet2'),
(6, NULL, 'Rent & Housing', 'expense', 'bi-house-door'),
(7, NULL, 'Groceries & Provisions', 'expense', 'bi-cart3'),
(8, NULL, 'Dining Out & Food Delivery', 'expense', 'bi-cup-straw'),
(9, NULL, 'Utilities & Bills', 'expense', 'bi-lightning-charge'),
(10, NULL, 'Shopping & Apparel', 'expense', 'bi-bag'),
(11, NULL, 'Transportation & Fuel', 'expense', 'bi-fuel-pump'),
(12, NULL, 'Entertainment & Subscriptions', 'expense', 'bi-film'),
(13, NULL, 'Healthcare & Pharmacy', 'expense', 'bi-heart-pulse'),
(14, NULL, 'Education & Books', 'expense', 'bi-book'),
(15, 1, 'Tech & Gadgets', 'expense', 'bi-cpu'),
(16, 1, 'Gym & Fitness', 'expense', 'bi-activity');

-- Seed Budgets for Rahul (September 2026)
INSERT INTO budgets (user_id, category_id, budget_amount, month, year) VALUES
(1, 6, 25000.00, 9, 2026),
(1, 7, 8000.00, 9, 2026),
(1, 8, 5000.00, 9, 2026),
(1, 9, 4500.00, 9, 2026),
(1, 10, 8000.00, 9, 2026),
(1, 11, 4000.00, 9, 2026),
(1, 12, 2000.00, 9, 2026);

-- Seed Transactions (June - September 2026)
INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) VALUES
(1, 1, 1, 85000.00, 'income', '2026-06-01', 'Monthly Salary - June'),
(1, 1, 6, 25000.00, 'expense', '2026-06-02', 'House Rent transfer to Owner'),
(1, 5, 7, 6800.00, 'expense', '2026-06-05', 'Monthly groceries from Nature Basket'),
(1, 3, 9, 3200.00, 'expense', '2026-06-10', 'Electricity & Airtel broadband bill'),
(1, 5, 8, 3400.00, 'expense', '2026-06-14', 'Weekend team dinner at Olive Bistro'),
(1, 3, 10, 5500.00, 'expense', '2026-06-20', 'Clothing sale on Myntra'),
(1, 2, 3, 4200.00, 'income', '2026-06-25', 'Mutual funds quarterly dividend'),
(1, 1, 1, 85000.00, 'income', '2026-07-01', 'Monthly Salary - July'),
(1, 1, 2, 28000.00, 'income', '2026-07-03', 'Freelance React web dashboard project'),
(1, 1, 6, 25000.00, 'expense', '2026-07-04', 'House Rent transfer to Owner'),
(1, 5, 7, 7200.00, 'expense', '2026-07-08', 'Supermarket grocery essentials'),
(1, 3, 15, 14500.00, 'expense', '2026-07-12', 'Noise Cancelling Headphones (Bose)'),
(1, 5, 11, 3200.00, 'expense', '2026-07-16', 'HPCL Petrol bunk fill-up'),
(1, 3, 12, 1199.00, 'expense', '2026-07-19', 'Netflix & Spotify annual recharge'),
(1, 4, 8, 2200.00, 'expense', '2026-07-24', 'Street food & coffee cafes'),
(1, 1, 1, 85000.00, 'income', '2026-08-01', 'Monthly Salary - August'),
(1, 1, 6, 25000.00, 'expense', '2026-08-02', 'House Rent transfer to Owner'),
(1, 5, 7, 7600.00, 'expense', '2026-08-06', 'Monthly Groceries - DMart'),
(1, 3, 9, 3450.00, 'expense', '2026-08-11', 'Tata Power bill & piped gas'),
(1, 5, 8, 4800.00, 'expense', '2026-08-15', 'Independence Day dining with friends'),
(1, 5, 11, 2900.00, 'expense', '2026-08-20', 'Fuel & cab rides'),
(1, 3, 13, 1850.00, 'expense', '2026-08-23', 'Apollo Pharmacy medicines & vitamins'),
(1, 2, 3, 5600.00, 'income', '2026-08-28', 'Fixed deposit interest credited'),
(1, 1, 1, 85000.00, 'income', '2026-09-01', 'Monthly Salary - September'),
(1, 1, 2, 18500.00, 'income', '2026-09-02', 'Python backend consulting project'),
(1, 1, 6, 25000.00, 'expense', '2026-09-02', 'House Rent transfer to Owner'),
(1, 5, 7, 4500.00, 'expense', '2026-09-05', 'Blinkit & Zepto groceries'),
(1, 3, 9, 2400.00, 'expense', '2026-09-08', 'Broadband and mobile postpaid bills'),
(1, 5, 8, 2800.00, 'expense', '2026-09-11', 'Family dinner at Barbeque Nation'),
(1, 3, 10, 9400.00, 'expense', '2026-09-14', 'Great Indian Festival online shopping'),
(1, 5, 11, 3300.00, 'expense', '2026-09-17', 'Fuel and Fastag recharge'),
(1, 5, 7, 3100.00, 'expense', '2026-09-20', 'Organic produce & dairy items'),
(1, 4, 8, 2950.00, 'expense', '2026-09-22', 'Weekend cafe outings with college friends'),
(1, 3, 12, 1250.00, 'expense', '2026-09-24', 'IMAX Movie tickets & popcorn'),
(1, 5, 16, 2500.00, 'expense', '2026-09-26', 'Gold Gym monthly membership renew'),
(1, 4, 5, 3000.00, 'income', '2026-09-27', 'Cash received from roommate for shared groceries'),
(2, 6, 1, 72000.00, 'income', '2026-09-01', 'Software Engineer Monthly Salary'),
(2, 6, 6, 20000.00, 'expense', '2026-09-03', 'Apartment Rent'),
(2, 7, 7, 5200.00, 'expense', '2026-09-07', 'Weekly groceries shopping'),
(2, 7, 8, 1800.00, 'expense', '2026-09-15', 'Italian restaurant lunch with friends');
