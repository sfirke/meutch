from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
import logging

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable debug mode
    app.debug = True

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    login.login_view = 'auth.login'  # Redirect to 'auth.login' when login is required

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    logger.debug(f'Registered main blueprint: {main_bp.name}')

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    logger.debug(f'Registered auth blueprint: {auth_bp.name}')

    # Log the URL map
    logger.debug(f'URL Map after blueprint registration: {app.url_map}')

    # Define user_loader
    from app.models import User  # Ensure User is imported

    @login.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app

from app import models  # Import models after app creation to avoid circular imports