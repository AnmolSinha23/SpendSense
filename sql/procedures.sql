-- ============================================================================
-- PROJECT: SpendSense - Personal & Group Expenditure Tracking System
-- MODULE: Stored Procedures for Transaction Management and Business Logic
-- DBMS: MySQL 8.0+
--
-- DBMS VIVA CONCEPT EXPLANATION:
-- Stored Procedures are pre-compiled SQL routines saved inside the database catalog.
-- Advantages in DBMS:
-- 1. Performance: Pre-compiled execution plans reduce parsing overhead.
-- 2. Network Traffic Reduction: Multiple database interactions happen locally on
--    the server in a single call instead of round-trips over the network.
-- 3. Security: Applications can be granted EXECUTE permissions on procedures
--    without giving direct INSERT/UPDATE table privileges (Principle of Least Privilege).
-- 4. ACID Transaction Control: Full programmatic control over START TRANSACTION,
--    COMMIT, and ROLLBACK with structured exception handling.
-- ============================================================================

USE spendsense_db;

DELIMITER $$

-- ----------------------------------------------------------------------------
-- PROCEDURE 1: sp_add_transaction
-- Purpose:
--   Atomically validates and registers a new transaction.
--   Enforces user ownership, category validity, and non-negative amounts.
--   Leverages MySQL transaction boundaries (ACID compliance) and works seamlessly
--   with trg_after_transaction_insert to update account balance.
-- Parameters:
--   IN  p_user_id       : ID of the authenticated user
--   IN  p_account_id    : Account linked to this transaction
--   IN  p_category_id   : Category of transaction
--   IN  p_amount        : Transaction value (> 0)
--   IN  p_txn_type      : 'income' or 'expense'
--   IN  p_txn_date      : Date of the transaction
--   IN  p_description   : Optional text note
--   OUT p_txn_id        : Generated transaction_id
--   OUT p_status_code   : 0 = Success, 1 = Invalid Input, 2 = Unauthorized/Not Found, 99 = Error
--   OUT p_status_msg    : Human-readable status message
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_add_transaction$$

CREATE PROCEDURE sp_add_transaction(
    IN  p_user_id      INT,
    IN  p_account_id   INT,
    IN  p_category_id  INT,
    IN  p_amount       DECIMAL(12, 2),
    IN  p_txn_type     VARCHAR(10),
    IN  p_txn_date     DATE,
    IN  p_description  VARCHAR(255),
    OUT p_txn_id       INT,
    OUT p_status_code  INT,
    OUT p_status_msg   VARCHAR(255)
)
proc_block: BEGIN
    DECLARE v_account_owner INT DEFAULT NULL;
    DECLARE v_category_valid INT DEFAULT 0;

    -- Exception Handler: Any SQL error triggers an automatic rollback
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_txn_id = NULL;
        SET p_status_code = 99;
        SET p_status_msg = 'Transaction failed: Database exception occurred. Changes rolled back.';
    END;

    -- 1. Input Validation: Check positive amount
    IF p_amount IS NULL OR p_amount <= 0 THEN
        SET p_txn_id = NULL;
        SET p_status_code = 1;
        SET p_status_msg = 'Validation error: Transaction amount must be strictly greater than zero.';
        LEAVE proc_block;
    END IF;

    -- 2. Input Validation: Check valid transaction type
    IF p_txn_type NOT IN ('income', 'expense') THEN
        SET p_txn_id = NULL;
        SET p_status_code = 1;
        SET p_status_msg = 'Validation error: Transaction type must be either income or expense.';
        LEAVE proc_block;
    END IF;

    -- 3. Authorization Check: Ensure the account belongs to this user
    SELECT user_id INTO v_account_owner
    FROM accounts
    WHERE account_id = p_account_id;

    IF v_account_owner IS NULL OR v_account_owner <> p_user_id THEN
        SET p_txn_id = NULL;
        SET p_status_code = 2;
        SET p_status_msg = 'Security violation: Selected account does not belong to the authenticated user.';
        LEAVE proc_block;
    END IF;

    -- 4. Category Check: Category must be global (user_id IS NULL) or owned by this user
    SELECT COUNT(*) INTO v_category_valid
    FROM categories
    WHERE category_id = p_category_id
      AND (user_id IS NULL OR user_id = p_user_id);

    IF v_category_valid = 0 THEN
        SET p_txn_id = NULL;
        SET p_status_code = 2;
        SET p_status_msg = 'Validation error: Invalid category specified.';
        LEAVE proc_block;
    END IF;

    -- 5. Atomic Insertion
    START TRANSACTION;

    INSERT INTO transactions (
        user_id,
        account_id,
        category_id,
        amount,
        txn_type,
        txn_date,
        description
    ) VALUES (
        p_user_id,
        p_account_id,
        p_category_id,
        p_amount,
        p_txn_type,
        p_txn_date,
        p_description
    );

    -- Capture the generated transaction_id
    SET p_txn_id = LAST_INSERT_ID();
    SET p_status_code = 0;
    SET p_status_msg = 'Transaction created successfully and balance updated.';

    -- Commit atomic block (trg_after_transaction_insert runs synchronously)
    COMMIT;
END proc_block$$


-- ----------------------------------------------------------------------------
-- PROCEDURE 2: sp_delete_transaction
-- Purpose:
--   Safely deletes a transaction while verifying user ownership.
--   When row is deleted, trg_after_transaction_delete automatically restores balance.
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_delete_transaction$$

CREATE PROCEDURE sp_delete_transaction(
    IN  p_user_id      INT,
    IN  p_txn_id       INT,
    OUT p_status_code  INT,
    OUT p_status_msg   VARCHAR(255)
)
del_block: BEGIN
    DECLARE v_owner INT DEFAULT NULL;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 99;
        SET p_status_msg = 'Deletion failed: Database error occurred. Changes rolled back.';
    END;

    -- Verify ownership
    SELECT user_id INTO v_owner
    FROM transactions
    WHERE transaction_id = p_txn_id;

    IF v_owner IS NULL THEN
        SET p_status_code = 2;
        SET p_status_msg = 'Transaction not found.';
        LEAVE del_block;
    END IF;

    IF v_owner <> p_user_id THEN
        SET p_status_code = 2;
        SET p_status_msg = 'Unauthorized: You cannot delete another user transaction.';
        LEAVE del_block;
    END IF;

    START TRANSACTION;
    DELETE FROM transactions WHERE transaction_id = p_txn_id AND user_id = p_user_id;
    COMMIT;

    SET p_status_code = 0;
    SET p_status_msg = 'Transaction deleted and account balance adjusted.';
END del_block$$


-- ----------------------------------------------------------------------------
-- PROCEDURE 3: sp_get_monthly_analytics
-- Purpose:
--   Calculates aggregated financial figures for a given user, month, and year.
--   Returns single-row summary: total_income, total_expense, net_savings, txn_count.
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_get_monthly_analytics$$

CREATE PROCEDURE sp_get_monthly_analytics(
    IN p_user_id INT,
    IN p_month   INT,
    IN p_year    INT
)
BEGIN
    SELECT
        COALESCE(SUM(CASE WHEN txn_type = 'income' THEN amount ELSE 0 END), 0.00) AS total_income,
        COALESCE(SUM(CASE WHEN txn_type = 'expense' THEN amount ELSE 0 END), 0.00) AS total_expense,
        COALESCE(SUM(CASE WHEN txn_type = 'income' THEN amount ELSE -amount END), 0.00) AS net_savings,
        COUNT(transaction_id) AS total_transactions
    FROM transactions
    WHERE user_id = p_user_id
      AND MONTH(txn_date) = p_month
      AND YEAR(txn_date) = p_year;
END$$

DELIMITER ;
