from flask_debugtoolbar import DebugToolbarExtension
from flask_sqlalchemy import SQLAlchemy
from flask_static_digest import FlaskStaticDigest
from flask_login import LoginManager
from flask_mail import Mail

debug_toolbar = DebugToolbarExtension()
db = SQLAlchemy()
flask_static_digest = FlaskStaticDigest()
login_manager = LoginManager()
mail = Mail()

def init_login_manager(app):
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        from calendarproject.models.user import User
        return User.query.get(int(user_id))

def init_mail(app):
    mail.init_app(app)