from flask import Flask
from werkzeug.debug import DebuggedApplication
from werkzeug.middleware.proxy_fix import ProxyFix
from celery import Celery
from celery import Task
from calendarproject.extensions import db, debug_toolbar, flask_static_digest, init_login_manager, init_mail
from calendarproject.page.views import page
from calendarproject.up.views import up
from calendarproject.auth.views import auth
from calendarproject.calendar.views import calendar
from calendarproject.admin.views import admin
from calendarproject.models.user import User
from calendarproject.instructor.views import instructor
from calendarproject.notifications.views import notifications
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv(".env.local", override=True)

def setup_logging(app):
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # Set up file handler
    file_handler = RotatingFileHandler('logs/calendarproject.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)

    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Add handlers to the app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

    app.logger.info('CalendarProject startup')


def create_celery_app(app=None):
    """
    Create a new Celery app and tie together the Celery config to the app's
    config. Wrap all tasks in the context of the application.

    :param app: Flask app
    :return: Celery app
    """
    app = app or create_app()

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(app.import_name, task_cls=FlaskTask)
    celery.conf.update(app.config.get("CELERY_CONFIG", {}))
    celery.set_default()
    app.extensions["celery"] = celery

    return celery


def create_app(settings_override=None):
    """
    Create a Flask application using the app factory pattern.
    """
    app = Flask(__name__, static_folder="../public", static_url_path="")

    app.config.from_object("config.settings")

    app.config['DEBUG_TB_ENABLED'] = False

    if settings_override:
        app.config.update(settings_override)

    middleware(app)

    app.register_blueprint(up)
    app.register_blueprint(page)
    app.register_blueprint(auth)
    app.register_blueprint(notifications)
    app.register_blueprint(calendar)
    app.register_blueprint(admin)
    app.register_blueprint(instructor)
    extensions(app)
    setup_logging(app)
    with app.app_context():
        db.create_all()
        create_admin_if_not_exists(app)

    return app


def extensions(app):
    """
    Register 0 or more extensions (mutates the app passed in).
    """
    debug_toolbar.init_app(app)
    db.init_app(app)
    flask_static_digest.init_app(app)
    init_login_manager(app)
    init_mail(app)
    return None


def middleware(app):
    """
    Register 0 or more middleware (mutates the app passed in).
    """
    # Enable the Flask interactive debugger in the browser for development.
    if app.debug:
        app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=True)

    # Set the real IP address into request.remote_addr when behind a proxy.
    app.wsgi_app = ProxyFix(app.wsgi_app)

    return None


def create_admin_if_not_exists(app):
    """
    Create an admin account if it doesn't exist.
    """
    # Use os.getenv directly with fallbacks
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_first_name = os.getenv("ADMIN_FIRST_NAME", "Jacek")
    admin_last_name = os.getenv("ADMIN_LAST_NAME", "Jeleń")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        print("Warning: ADMIN_PASSWORD environment variable is not set!")
        admin_password = "change_me_immediately"  # Default fallback

    with app.app_context():
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            new_admin = User(
                username=admin_username,
                email=admin_email,
                first_name=admin_first_name,
                last_name=admin_last_name,
                is_admin=True
            )
            new_admin.set_password(admin_password)
            db.session.add(new_admin)
            db.session.commit()
            print("Konto admina zostało utworzone.")
        else:
            print("Konto admina już istnieje.")


celery_app = create_celery_app()
