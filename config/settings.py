import os
from distutils.util import strtobool
from dotenv import load_dotenv
load_dotenv()
load_dotenv(".env.local", override=True)
SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = bool(strtobool(os.getenv("FLASK_DEBUG", "false")))

print(os.getenv("SERVER_NAME"),"xd")
SERVER_NAME = os.getenv("SERVER_NAME") if os.getenv("SERVER_NAME") else None

# Admin configuration
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_FIRST_NAME = os.getenv("ADMIN_FIRST_NAME", "Jacek")
ADMIN_LAST_NAME = os.getenv("ADMIN_LAST_NAME", "Jeleń")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# SQLAlchemy.
pg_user = os.getenv("POSTGRES_USER")
pg_pass = os.getenv("POSTGRES_PASSWORD")
pg_host = os.getenv("POSTGRES_HOST", "postgres")
pg_port = os.getenv("POSTGRES_PORT", "5432")
pg_db = os.getenv("POSTGRES_DB", pg_user)
db = f"postgresql+psycopg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", db)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Mail settings
MAIL_SERVER = 'poczta.interia.pl'
MAIL_PORT = 465
MAIL_USE_TLS = True
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "random")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "random")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "random")  # Fixed this line

# Redis.
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DEBUG_TB_INTERCEPT_REDIRECTS = False

# Celery.
CELERY_CONFIG = {
    "broker_url": REDIS_URL,
    "result_backend": REDIS_URL,
    "include": [],
}