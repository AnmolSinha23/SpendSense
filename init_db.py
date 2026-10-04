"""
SpendSense - Database Initialization Script
Executes the master SQL script (schema, triggers, stored procedures, views, seed data)
using mysql-connector-python without requiring MySQL Workbench or mysql CLI.
"""

import sys
import os
import mysql.connector
from mysql.connector import Error
from config import Config


def parse_sql_statements(content):
    """
    Parses a multi-statement SQL string, correctly handling MySQL DELIMITER $$ blocks
    used in triggers and stored procedures.
    """
    statements = []
    delimiter = ';'
    current_statement = []

    for line in content.splitlines():
        stripped = line.strip()

        # Handle comments and empty lines outside statements
        if not current_statement and (stripped.startswith('--') or stripped.startswith('/*') or not stripped):
            continue

        # Check for DELIMITER keyword change
        if stripped.upper().startswith('DELIMITER'):
            parts = stripped.split()
            if len(parts) > 1:
                delimiter = parts[1].strip()
            continue

        if delimiter != ';' and stripped.endswith(delimiter):
            # Strip delimiter and finalize block
            end_idx = line.rfind(delimiter)
            current_statement.append(line[:end_idx])
            stmt_text = '\n'.join(current_statement).strip()
            if stmt_text:
                statements.append(stmt_text)
            current_statement = []
        elif delimiter == ';' and stripped.endswith(';'):
            current_statement.append(line)
            stmt_text = '\n'.join(current_statement).strip()
            if stmt_text:
                statements.append(stmt_text)
            current_statement = []
        else:
            current_statement.append(line)

    return statements


def initialize_database():
    print("=" * 65)
    print(" SpendSense - MySQL Database Initializer")
    print("=" * 65)
    print(f"Connecting to MySQL Server at {Config.DB_HOST}:{Config.DB_PORT} as '{Config.DB_USER}'...")

    try:
        # Step 1: Connect to MySQL server (without specifying database first)
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            autocommit=True
        )
        cursor = conn.cursor()
        print(" Connected to MySQL Server successfully!")

        # Step 2: Read SQL file
        sql_file_path = os.path.join(os.path.dirname(__file__), 'sql', 'setup_database.sql')
        if not os.path.exists(sql_file_path):
            print(f" Error: Setup script not found at: {sql_file_path}")
            return False

        print(f"Reading SQL script from: {sql_file_path}...")
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        statements = parse_sql_statements(sql_content)
        print(f"Parsed {len(statements)} SQL statements (DDL, Triggers, Procedures, Views, Seeds).")

        # Step 3: Execute each statement
        success_count = 0
        for i, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
                success_count += 1
            except Error as e:
                # Print specific error context
                preview = stmt.strip().split('\n')[0][:70]
                print(f" [Warning/Error on stmt {i}] {preview}...")
                print(f"   Details: {e}")

        cursor.close()
        conn.close()

        print("=" * 65)
        print(f" Database setup finished! ({success_count}/{len(statements)} statements executed)")
        print(f" Database '{Config.DB_NAME}' is ready with 3NF Schema, Triggers, Views & Demo Data.")
        print(" Demo credentials:")
        print("   Email:    rahul@example.com")
        print("   Password: Password@123")
        print("=" * 65)
        return True

    except Error as err:
        print(f"\n MySQL Error: {err}")
        print("\nTroubleshooting:")
        print("1. Ensure MySQL Server is running (Service: MySQL80).")
        print("2. Check your password in .env (DB_PASSWORD=your_mysql_password).")
        print("3. Check your user in .env (DB_USER=root).")
        print("=" * 65)
        return False


if __name__ == '__main__':
    initialize_database()
