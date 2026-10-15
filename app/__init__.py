from flask import Flask
from app.config import Config
from app import database
import os

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize database
    database.init_app(app)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.sales import sales_bp
    from app.routes.history import history_bp
    from app.routes.imports import imports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(imports_bp)

    # Template filters
    @app.template_filter('currency')
    def format_currency(value):
        try:
            return f"₱{float(value):,.2f}"
        except (ValueError, TypeError):
            return f"₱0.00"

    @app.template_filter('number')
    def format_number(value):
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return str(value)

    return app
