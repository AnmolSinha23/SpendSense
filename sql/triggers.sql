-- ============================================================================
-- PROJECT: SpendSense - Personal & Group Expenditure Tracking System
-- MODULE: Database Triggers for Automated Balance Synchronization
-- DBMS: MySQL 8.0+
--
-- DBMS VIVA CONCEPT EXPLANATION:
-- A database trigger is a procedural code block automatically executed by the
-- DBMS engine in response to specific DML events (INSERT, UPDATE, DELETE) on a table.
--
-- Why Triggers for Balance Management?
-- 1. Encapsulation: The business rule "transactions mutate account balances"
--    is enforced directly at the database tier.
-- 2. Consistency & Integrity: Even if an external script, developer shell,
--    or different application enters a transaction, the account balance is
--    guaranteed to stay perfectly synchronized.
-- 3. Atomicity: The trigger executes inside the same transaction boundary
--    as the triggering DML statement. If the trigger fails, the transaction is rolled back.
-- ============================================================================

USE spendsense_db;

DELIMITER $$

-- ----------------------------------------------------------------------------
-- TRIGGER 1: trg_after_transaction_insert
-- Event: AFTER INSERT ON transactions
-- Purpose:
--   Automatically updates the corresponding account's balance:
--   - If new transaction is 'income': credit balance (+ NEW.amount)
--   - If new transaction is 'expense': debit balance (- NEW.amount)
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_after_transaction_insert$$

CREATE TRIGGER trg_after_transaction_insert
AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    IF NEW.txn_type = 'income' THEN
        UPDATE accounts
        SET balance = balance + NEW.amount
        WHERE account_id = NEW.account_id;
    ELSEIF NEW.txn_type = 'expense' THEN
        UPDATE accounts
        SET balance = balance - NEW.amount
        WHERE account_id = NEW.account_id;
    END IF;
END$$


-- ----------------------------------------------------------------------------
-- TRIGGER 2: trg_after_transaction_update
-- Event: AFTER UPDATE ON transactions
-- Purpose:
--   Handles all possible modifications to a transaction:
--   1. Amount change (e.g., edited from $50 to $75)
--   2. Type change (e.g., switched from 'expense' to 'income')
--   3. Account change (e.g., paid from Credit Card instead of Bank Account)
--
-- Logic:
--   Phase A: Reverse the financial impact of OLD values on OLD.account_id.
--   Phase B: Apply the financial impact of NEW values on NEW.account_id.
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_after_transaction_update$$

CREATE TRIGGER trg_after_transaction_update
AFTER UPDATE ON transactions
FOR EACH ROW
BEGIN
    -- Phase A: Undo the OLD transaction from the old account
    IF OLD.txn_type = 'income' THEN
        UPDATE accounts
        SET balance = balance - OLD.amount
        WHERE account_id = OLD.account_id;
    ELSEIF OLD.txn_type = 'expense' THEN
        UPDATE accounts
        SET balance = balance + OLD.amount
        WHERE account_id = OLD.account_id;
    END IF;

    -- Phase B: Apply the NEW transaction to the new account
    IF NEW.txn_type = 'income' THEN
        UPDATE accounts
        SET balance = balance + NEW.amount
        WHERE account_id = NEW.account_id;
    ELSEIF NEW.txn_type = 'expense' THEN
        UPDATE accounts
        SET balance = balance - NEW.amount
        WHERE account_id = NEW.account_id;
    END IF;
END$$


-- ----------------------------------------------------------------------------
-- TRIGGER 3: trg_after_transaction_delete
-- Event: AFTER DELETE ON transactions
-- Purpose:
--   Reverses the financial impact when a transaction is deleted:
--   - Deleting an 'income' row reverses the credit: balance decreases (- OLD.amount)
--   - Deleting an 'expense' row reverses the debit: balance is restored (+ OLD.amount)
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_after_transaction_delete$$

CREATE TRIGGER trg_after_transaction_delete
AFTER DELETE ON transactions
FOR EACH ROW
BEGIN
    IF OLD.txn_type = 'income' THEN
        UPDATE accounts
        SET balance = balance - OLD.amount
        WHERE account_id = OLD.account_id;
    ELSEIF OLD.txn_type = 'expense' THEN
        UPDATE accounts
        SET balance = balance + OLD.amount
        WHERE account_id = OLD.account_id;
    END IF;
END$$

DELIMITER ;
