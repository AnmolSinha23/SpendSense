-- ============================================================================
-- PROJECT: SpendSense - Personal & Group Expenditure Tracking System
-- MODULE: Database Schema Definition (DDL)
-- NORMALIZATION: Normalized to 3rd Normal Form (3NF)
-- DBMS: MySQL 8.0+
-- ============================================================================

-- Create Database if not exists
CREATE DATABASE IF NOT EXISTS spendsense_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE spendsense_db;

-- ----------------------------------------------------------------------------
-- 1. USERS TABLE
-- Description: Stores registered user credentials and profile information.
-- 3NF Justification:
--   - 1NF: All attributes are atomic (single values).
--   - 2NF: The primary key (user_id) is a single column; no partial dependencies.
--   - 3NF: No transitive dependencies; non-key attributes (name, email, password_hash)
--     depend solely on the candidate key (user_id or email).
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS budgets;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS users;

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

-- ----------------------------------------------------------------------------
-- 2. ACCOUNTS TABLE
-- Description: Represents user financial accounts (Cash, Bank, Credit Card, UPI, etc.)
-- 3NF Justification:
--   - Each account has an independent balance linked strictly to the account_id.
--   - user_id establishes relationship without redundant user details.
-- Constraints:
--   - Foreign key to users with ON DELETE CASCADE: if user deletes profile,
--     all their associated accounts are wiped out.
-- ----------------------------------------------------------------------------
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

-- ----------------------------------------------------------------------------
-- 3. CATEGORIES TABLE
-- Description: Transaction categories (Food, Rent, Salary, Freelance, etc.)
-- Design Pattern (Default vs Custom Categories):
--   - If user_id IS NULL: Category is a Global System Default (available to all users).
--   - If user_id IS NOT NULL: Category is a Custom Category created by that specific user.
-- 3NF Justification:
--   - Eliminates redundant category names across transactions.
--   - category_type is strictly either 'income' or 'expense'.
-- ----------------------------------------------------------------------------
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

-- ----------------------------------------------------------------------------
-- 4. TRANSACTIONS TABLE
-- Description: Core ledger recording financial flows (Income & Expense).
-- 3NF Justification:
--   - Contains only foreign keys (user_id, account_id, category_id) and transaction-specific
--     attributes (amount, txn_type, txn_date, description).
--   - No transient account names or category types stored here (prevents update anomalies).
-- Constraints:
--   - amount MUST be strictly positive (CHECK constraint).
--   - ON DELETE CASCADE for users and accounts ensures relational integrity.
--   - ON DELETE RESTRICT on categories prevents accidental deletion of categories in use.
-- ----------------------------------------------------------------------------
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

-- Indexes for optimal query performance on dashboard and reports
CREATE INDEX idx_transactions_user_date ON transactions(user_id, txn_date DESC);
CREATE INDEX idx_transactions_account ON transactions(account_id);
CREATE INDEX idx_transactions_category ON transactions(category_id);

-- ----------------------------------------------------------------------------
-- 5. BUDGETS TABLE
-- Description: Monthly budget ceilings set by users for specific expense categories.
-- 3NF Justification:
--   - Stores budget limits per (user_id, category_id, month, year) combo.
--   - UNIQUE constraint prevents duplicate budget rows for the same category in the same month.
-- ----------------------------------------------------------------------------
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
