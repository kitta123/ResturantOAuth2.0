import os
from app import app


WTF_CSRF_ENABLED = False
SECRET_KEY = '5de9c0bd407f8bfe10b1bcee5b11053e'

basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_respository')

# Configuration
GOOGLE_CLIENT_ID = "753250404195-503g9echg9dgh4vn1fmvdrgpe4vuahhq.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "7KBv6LpFdmqUqSwdr1uz6E5J"
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

# EMAIL SETTINGS
MAIL_SERVER = 'smtp.gmail.com',
MAIL_PORT = 465,
MAIL_USE_SSL = True,
Mail_USE_TLS= False,
USERNAME = 'kkma3.rymec@gmail.com',
PASSWORD = 'K8495977557'

app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
