import logging
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import config
from uuid import UUID
from app.context_processors import (
    inject_unread_messages_count, 
    inject_total_pending,
    inject_distance_utils
)


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=None):
    app = Flask(__name__)
    
    # Auto-detect environment if no config provided
    if config_class is None:
        flask_env = os.environ.get('FLASK_ENV', 'development')
        config_class = config.get(flask_env, config['default'])
    
    app.config.from_object(config_class)
    
    # Validate storage configuration at startup
    if hasattr(config_class, 'validate_storage_config'):
        config_instance = config_class()
        config_instance.validate_storage_config()

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    configure_logging(app)

    # Set the login view for @login_required
    login_manager.login_view = 'auth.login'
    
    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.circles import bp as circles_bp
    app.register_blueprint(circles_bp, url_prefix='/circles')

    # Register CLI commands
    try:
        from app.cli import seed, check_loan_reminders
        app.cli.add_command(seed)
        app.cli.add_command(check_loan_reminders)
    except ImportError as e:
        print(f"Warning: Could not import CLI commands: {e}")

    # Define the user loader callback
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        try:
            uuid_obj = UUID(user_id, version=4)
        except ValueError:
            return None
        return db.session.get(User, uuid_obj)
    
    # Register the context processor
    app.context_processor(inject_unread_messages_count)
    app.context_processor(inject_total_pending)
    app.context_processor(inject_distance_utils)
    
    # Auto-seed development database if empty
    with app.app_context():
        if app.config.get('FLASK_ENV') == 'development':
            try:
                from app.models import User
                # First check if tables exist by trying a simple query
                try:
                    user_count = User.query.count()
                    if user_count == 0:
                        print("🌱 Development database is empty, auto-seeding...")
                        from app.utils.data_seeding import check_and_seed_if_empty
                        check_and_seed_if_empty()
                except Exception as table_error:
                    print(f"Note: Database tables not ready for auto-seeding: {table_error}")
                    print("💡 Run 'flask db upgrade' to create tables, then restart the app.")
            except Exception as e:
                print(f"Note: Could not check/seed database: {e}")

    return app


def configure_logging(app):
    # Remove the default Flask logger handlers
    del app.logger.handlers[:]
    
    # Create a new logger handler
    handler = logging.StreamHandler()
    handler.setLevel(app.config['LOG_LEVEL'])

    # Define log format
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    handler.setFormatter(formatter)

    # Add the handler to the app's logger
    app.logger.addHandler(handler)
    app.logger.setLevel(app.config['LOG_LEVEL'])

    # Optional: Disable werkzeug's default logger if necessary
    # logging.getLogger('werkzeug').setLevel(logging.ERROR)