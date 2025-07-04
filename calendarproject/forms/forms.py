from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Length

class LoginForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[DataRequired(message='To pole jest wymagane')])
    password = PasswordField('Hasło', validators=[DataRequired(message='To pole jest wymagane')])

class RegisterForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(min=4, max=20, message='Nazwa użytkownika musi mieć od 4 do 20 znaków')
    ])
    email = StringField('Adres email', validators=[
        DataRequired(message='To pole jest wymagane'),
        Email(message='Nieprawidłowy adres email')
    ])
    password = PasswordField('Hasło', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(min=6, message='Hasło musi mieć co najmniej 6 znaków')
    ])
    first_name = StringField('Imię', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(max=50, message='Imię nie może przekraczać 50 znaków')
    ])
    last_name = StringField('Nazwisko', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(max=50, message='Nazwisko nie może przekraczać 50 znaków')
    ])

class CreateInstructorForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(min=4, max=20, message='Nazwa użytkownika musi mieć od 4 do 20 znaków')
    ])
    email = StringField('Adres email', validators=[
        DataRequired(message='To pole jest wymagane'),
        Email(message='Nieprawidłowy adres email')
    ])
    password = PasswordField('Hasło', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(min=6, message='Hasło musi mieć co najmniej 6 znaków')
    ])
    first_name = StringField('Imię', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(max=50, message='Imię nie może przekraczać 50 znaków')
    ])
    last_name = StringField('Nazwisko', validators=[
        DataRequired(message='To pole jest wymagane'),
        Length(max=50, message='Nazwisko nie może przekraczać 50 znaków')
    ])