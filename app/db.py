"""
SpendSense - Database Access Layer
Implements raw SQL communication with MySQL using mysql-connector-python.
NO ORMs (like SQLAlchemy) are used, adhering strictly to DBMS coursework requirements.

All queries use parameterized statements (%s) to guarantee protection against SQL Injection.
Database connections are managed per-request using Flask's application context (`g`).
"""

import mysql.connector
from mysql.connector import Error
from flask import g, current_app
from config import Config


def get_db():
    """
    Returns an active MySQL database connection for the current request context.
    Caches connection in Flask's `g` object to prevent redundant connections.
    """
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                autocommit=False  # Explicit transaction control for ACID guarantees
            )
        except Error as err:
            # If database doesn't exist yet, connect without db to allow initialization
            if err.errno == 1049:  # ER_BAD_DB_ERROR
                g.db = mysql.connector.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    autocommit=True
                )
            else:
                raise err
    return g.db


def close_db(e=None):
    """
    Closes the MySQL database connection at the end of the HTTP request lifecycle.
    Registered with Flask's teardown_appcontext.
    """
    db = g.pop('db', None)
    if db is not None and db.is_connected():
        db.close()


def query_db(query, params=(), one=False, commit=False):
    """
    Executes a raw SQL statement with parameter binding.

    Parameters:
        query (str): The parameterized SQL query string.
        params (tuple or list): Values to bind safely to %s placeholders.
        one (bool): If True, returns only the first row matching the query.
        commit (bool): If True, commits the transaction immediately (for INSERT/UPDATE/DELETE).

    Returns:
        list of dicts (or single dict if one=True, or lastrowid/affected_rows on write).
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        if commit:
            db.commit()
            return cursor.lastrowid
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv
    except Error as err:
        if commit:
            db.rollback()
        raise err
    finally:
        cursor.close()


def execute_procedure(proc_name, params=()):
    """
    Executes a MySQL Stored Procedure using cursor.callproc().
    Safely captures output parameters and returned result sets.

    Parameters:
        proc_name (str): Name of the stored procedure in MySQL.
        params (list or tuple): IN and OUT arguments to pass to the procedure.

    Returns:
        tuple: (out_params, result_sets)
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # callproc passes arguments and populates OUT parameters
        proc_results = cursor.callproc(proc_name, params)
        db.commit()

        # Fetch any SELECT result sets returned by the procedure
        result_sets = []
        for result in cursor.stored_results():
            result_sets.append(result.fetchall())

        return proc_results, result_sets
    except Error as err:
        db.rollback()
        raise err
    finally:
        cursor.close()


def execute_sql_script(file_path):
    """
    Executes a multi-statement SQL script file (e.g., schema.sql, seed.sql).
    Useful for initializing or resetting the database catalog.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Handle MySQL DELIMITER $$ syntax for triggers and procedures
        statements = []
        delimiter = ';'
        current_stmt = []

        for line in sql_content.splitlines():
            trimmed = line.strip()
            if trimmed.upper().startswith('DELIMITER'):
                parts = trimmed.split()
                if len(parts) > 1:
                    delimiter = parts[1]
                continue

            if delimiter != ';' and trimmed.endswith(delimiter):
                current_stmt.append(line[:line.rfind(delimiter)])
                stmt_text = '\n'.join(current_stmt).strip()
                if stmt_text:
                    statements.append(stmt_text)
                current_stmt = []
            elif delimiter == ';' and trimmed.endswith(';'):
                current_stmt.append(line)
                stmt_text = '\n'.join(current_stmt).strip()
                if stmt_text:
                    statements.append(stmt_text)
                current_stmt = []
            else:
                current_stmt.append(line)

        for stmt in statements:
            if stmt.strip():
                cursor.execute(stmt)

        db.commit()
        return True
    except Error as err:
        db.rollback()
        raise err
    finally:
        cursor.close()
