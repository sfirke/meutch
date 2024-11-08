import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import Config
from uuid import UUID

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Set the login view for @login_required
    login_manager.login_view = 'auth.login'
    
    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.circles import bp as circles_bp
    app.register_blueprint(circles_bp, url_prefix='/circles')
    
    # Define the user loader callback
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        try:
            uuid_obj = UUID(user_id, version=4)
        except ValueError:
            return None
        return User.query.get(uuid_obj)
    
    return app