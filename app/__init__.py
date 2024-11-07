from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import Config
import logging

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable debug mode
    app.debug = True

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    login.login_view = 'auth.login'
    csrf.init_app(app)

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.circles import bp as circles_bp
    app.register_blueprint(circles_bp, url_prefix='/circles')

    # Log the URL map
    logger.debug(f'URL Map after blueprint registration: {app.url_map}')

    # Define user_loader
    from app.models import User  # Ensure User is imported

    @login.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app