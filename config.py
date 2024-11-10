import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-this'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DO_SPACES_REGION = os.environ.get('DO_SPACES_REGION')
    DO_SPACES_ENDPOINT = f'https://{DO_SPACES_REGION}.digitaloceanspaces.com'
    DO_SPACES_KEY = os.environ.get('DO_SPACES_KEY')
    DO_SPACES_SECRET = os.environ.get('DO_SPACES_SECRET')
    DO_SPACES_BUCKET = os.environ.get('DO_SPACES_BUCKET')

    LOG_LEVEL = 'INFO'  # Set to DEBUG to see all logs
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'app.log'