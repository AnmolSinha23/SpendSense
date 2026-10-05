"""
SpendSense - Flask Application Factory
Initializes configuration, registers database teardown handlers, custom Jinja filters,
and attaches modular Route Blueprints.
"""

from flask import Flask
from config import Config
from app.db import close_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register Database connection teardown
    app.teardown_appcontext(close_db)

    # Custom Jinja filters for formatting
    @app.template_filter('currency')
    def currency_filter(value):
        try:
            val = float(value or 0)
            if val < 0:
                return f"-₹{abs(val):,.2f}"
            return f"₹{val:,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"

    @app.template_filter('abs_currency')
    def abs_currency_filter(value):
        try:
            val = abs(float(value or 0))
            return f"₹{val:,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"

    @app.template_filter('format_date')
    def format_date_filter(value):
        if hasattr(value, 'strftime'):
            return value.strftime("%d %b %Y")
        return str(value)

    app.jinja_env.globals['hasattr'] = hasattr

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.accounts import accounts_bp
    from app.routes.transactions import transactions_bp
    from app.routes.categories import categories_bp
    from app.routes.budgets import budgets_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(reports_bp)

    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    oauth.register(
        name='google',
        server_metadata_url=app.config.get('GOOGLE_DISCOVERY_URL', 'https://accounts.google.com/.well-known/openid-configuration'),
        client_kwargs={'scope': 'openid email profile'}
    )
    app.oauth = oauth

    return app
