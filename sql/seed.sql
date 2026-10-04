-- ============================================================================
-- PROJECT: SpendSense - Personal & Group Expenditure Tracking System
-- MODULE: Realistic Seed / Demo Data Script
-- DBMS: MySQL 8.0+
-- NOTE:
--   Default password for demo accounts is: Password@123
--   The hash was generated via Werkzeug security (scrypt algorithm).
--   Because trg_after_transaction_insert is active, inserting these transactions
--   will automatically update each account's live balance via the trigger!
-- ============================================================================

USE spendsense_db;

-- ----------------------------------------------------------------------------
-- 1. SEED USERS
-- ----------------------------------------------------------------------------
INSERT INTO users (user_id, name, email, password_hash, created_at) VALUES
(1, 'Rahul Sharma', 'rahul@example.com', 'scrypt:32768:8:1$lYUQeHrOYZMDGVo2$50dd391a132f80708aabcbf5e7caceccb5c31cbedbab09c5856aef7b949acf66fbe52bf7dc901648b0a7b66c3076778d065dda575c5a2b0fc81892c95ea831dc', '2026-06-01 10:00:00'),
(2, 'Priya Patel', 'priya@example.com', 'scrypt:32768:8:1$lYUQeHrOYZMDGVo2$50dd391a132f80708aabcbf5e7caceccb5c31cbedbab09c5856aef7b949acf66fbe52bf7dc901648b0a7b66c3076778d065dda575c5a2b0fc81892c95ea831dc', '2026-07-01 11:30:00');

-- ----------------------------------------------------------------------------
-- 2. SEED ACCOUNTS
-- Starting balance is initialized to 0.00; the triggers will calculate the real
-- live balance as transactions are entered below!
-- ----------------------------------------------------------------------------
INSERT INTO accounts (account_id, user_id, account_name, account_type, balance, created_at) VALUES
(1, 1, 'HDFC Salary Account', 'Bank', 0.00, '2026-06-01 10:05:00'),
(2, 1, 'SBI Savings', 'Savings', 0.00, '2026-06-01 10:10:00'),
(3, 1, 'ICICI Amazon Pay Card', 'Credit Card', 0.00, '2026-06-01 10:15:00'),
(4, 1, 'Cash Wallet', 'Cash', 0.00, '2026-06-01 10:20:00'),
(5, 1, 'Google Pay UPI', 'UPI', 0.00, '2026-06-01 10:25:00'),
(6, 2, 'Kotak Mahindra Bank', 'Bank', 0.00, '2026-07-01 11:35:00'),
(7, 2, 'Paytm Wallet', 'UPI', 0.00, '2026-07-01 11:40:00');

-- ----------------------------------------------------------------------------
-- 3. SEED CATEGORIES (Global Defaults + User Custom Categories)
-- user_id = NULL indicates Global default categories.
-- user_id = 1 indicates Rahul's custom categories.
-- ----------------------------------------------------------------------------
INSERT INTO categories (category_id, user_id, category_name, category_type, icon) VALUES
-- Default Income Categories
(1, NULL, 'Salary', 'income', 'bi-cash-stack'),
(2, NULL, 'Freelance & Consulting', 'income', 'bi-laptop'),
(3, NULL, 'Investments & Dividends', 'income', 'bi-graph-up'),
(4, NULL, 'Gifts & Grants', 'income', 'bi-gift'),
(5, NULL, 'Other Income', 'income', 'bi-wallet2'),

-- Default Expense Categories
(6, NULL, 'Rent & Housing', 'expense', 'bi-house-door'),
(7, NULL, 'Groceries & Provisions', 'expense', 'bi-cart3'),
(8, NULL, 'Dining Out & Food Delivery', 'expense', 'bi-cup-straw'),
(9, NULL, 'Utilities & Bills', 'expense', 'bi-lightning-charge'),
(10, NULL, 'Shopping & Apparel', 'expense', 'bi-bag'),
(11, NULL, 'Transportation & Fuel', 'expense', 'bi-fuel-pump'),
(12, NULL, 'Entertainment & Subscriptions', 'expense', 'bi-film'),
(13, NULL, 'Healthcare & Pharmacy', 'expense', 'bi-heart-pulse'),
(14, NULL, 'Education & Books', 'expense', 'bi-book'),

-- Custom Categories for Rahul (User 1)
(15, 1, 'Tech & Gadgets', 'expense', 'bi-cpu'),
(16, 1, 'Gym & Fitness', 'expense', 'bi-activity');

-- ----------------------------------------------------------------------------
-- 4. SEED BUDGETS FOR RAHUL (SEPTEMBER 2026)
-- Provides a realistic variety of budget states (On Track, Warning, Exceeded)
-- ----------------------------------------------------------------------------
INSERT INTO budgets (user_id, category_id, budget_amount, month, year) VALUES
(1, 6, 25000.00, 9, 2026), -- Rent (Fixed: 25,000 / 25,000 -> 100%)
(1, 7, 8000.00, 9, 2026),  -- Groceries (Target: 8,000)
(1, 8, 5000.00, 9, 2026),  -- Dining Out (Target: 5,000)
(1, 9, 4500.00, 9, 2026),  -- Utilities (Target: 4,500)
(1, 10, 8000.00, 9, 2026), -- Shopping (Target: 8,000)
(1, 11, 4000.00, 9, 2026), -- Transportation (Target: 4,000)
(1, 12, 2000.00, 9, 2026); -- Entertainment (Target: 2,000)

-- ----------------------------------------------------------------------------
-- 5. SEED TRANSACTIONS (Spanning June, July, August, and September 2026)
-- ----------------------------------------------------------------------------
-- June 2026 Transactions (User 1: Rahul)
INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) VALUES
(1, 1, 1, 85000.00, 'income', '2026-06-01', 'Monthly Salary - June'),
(1, 1, 6, 25000.00, 'expense', '2026-06-02', 'House Rent transfer to Owner'),
(1, 5, 7, 6800.00, 'expense', '2026-06-05', 'Monthly groceries from Nature Basket'),
(1, 3, 9, 3200.00, 'expense', '2026-06-10', 'Electricity & Airtel broadband bill'),
(1, 5, 8, 3400.00, 'expense', '2026-06-14', 'Weekend team dinner at Olive Bistro'),
(1, 3, 10, 5500.00, 'expense', '2026-06-20', 'Clothing sale on Myntra'),
(1, 2, 3, 4200.00, 'income', '2026-06-25', 'Mutual funds quarterly dividend');

-- July 2026 Transactions (User 1: Rahul)
INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) VALUES
(1, 1, 1, 85000.00, 'income', '2026-07-01', 'Monthly Salary - July'),
(1, 1, 2, 28000.00, 'income', '2026-07-03', 'Freelance React web dashboard project'),
(1, 1, 6, 25000.00, 'expense', '2026-07-04', 'House Rent transfer to Owner'),
(1, 5, 7, 7200.00, 'expense', '2026-07-08', 'Supermarket grocery essentials'),
(1, 3, 15, 14500.00, 'expense', '2026-07-12', 'Noise Cancelling Headphones (Bose)'),
(1, 5, 11, 3200.00, 'expense', '2026-07-16', 'HPCL Petrol bunk fill-up'),
(1, 3, 12, 1199.00, 'expense', '2026-07-19', 'Netflix & Spotify annual recharge'),
(1, 4, 8, 2200.00, 'expense', '2026-07-24', 'Street food & coffee cafes');

-- August 2026 Transactions (User 1: Rahul)
INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) VALUES
(1, 1, 1, 85000.00, 'income', '2026-08-01', 'Monthly Salary - August'),
(1, 1, 6, 25000.00, 'expense', '2026-08-02', 'House Rent transfer to Owner'),
(1, 5, 7, 7600.00, 'expense', '2026-08-06', 'Monthly Groceries - DMart'),
(1, 3, 9, 3450.00, 'expense', '2026-08-11', 'Tata Power bill & piped gas'),
(1, 5, 8, 4800.00, 'expense', '2026-08-15', 'Independence Day dining with friends'),
(1, 5, 11, 2900.00, 'expense', '2026-08-20', 'Fuel & cab rides'),
(1, 3, 13, 1850.00, 'expense', '2026-08-23', 'Apollo Pharmacy medicines & vitamins'),
(1, 2, 3, 5600.00, 'income', '2026-08-28', 'Fixed deposit interest credited');

-- September 2026 Transactions (Current Month - User 1: Rahul)
-- Note how the expenses interact with the September budgets:
-- Groceries: 4500 + 3100 = 7600 (Budget 8,000 -> 95.0% WARNING)
-- Dining Out: 2800 + 2950 = 5750 (Budget 5,000 -> 115.0% EXCEEDED)
-- Shopping: 9400 (Budget 8,000 -> 117.5% EXCEEDED)
-- Utilities: 2400 (Budget 4,500 -> 53.3% ON TRACK)
-- Transportation: 3300 (Budget 4,000 -> 82.5% WARNING)
-- Entertainment: 1250 (Budget 2,000 -> 62.5% ON TRACK)
INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) VALUES
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
(1, 4, 5, 3000.00, 'income', '2026-09-27', 'Cash received from roommate for shared groceries');

-- Seed Data for User 2 (Priya)
INSERT INTO transactions (user_id, account_id, category_id, amount, txn_type, txn_date, description) VALUES
(2, 6, 1, 72000.00, 'income', '2026-09-01', 'Software Engineer Monthly Salary'),
(2, 6, 6, 20000.00, 'expense', '2026-09-03', 'Apartment Rent'),
(2, 7, 7, 5200.00, 'expense', '2026-09-07', 'Weekly groceries shopping'),
(2, 7, 8, 1800.00, 'expense', '2026-09-15', 'Italian restaurant lunch with friends');
