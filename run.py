"""
SpendSense - Application Entry Point
Starts the Flask WSGI development server.
"""

from app import create_app
from config import Config

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print(" SpendSense - Expenditure Tracking System")
    print(" DBMS College Semester Project (Python + Flask + MySQL)")
    print("=" * 60)
    print(f" * Server running on: http://127.0.0.1:5000")
    print(f" * Database Host:     {Config.DB_HOST}:{Config.DB_PORT}")
    print(f" * Database Name:     {Config.DB_NAME}")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=Config.DEBUG)
