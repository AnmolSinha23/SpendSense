"""
SpendSense - Application Configuration Module
Loads environment variables and encapsulates MySQL and Flask application settings.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file into environment
load_dotenv()

class Config:
    # Flask Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "spendsense_dev_secret_key_change_in_production")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    # MySQL Database Connection Settings (Raw SQL with mysql-connector-python)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "spendsense_db")
