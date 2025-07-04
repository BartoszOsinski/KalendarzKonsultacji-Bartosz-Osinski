from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from calendarproject.models.user import User
from calendarproject.extensions import db
from calendarproject.forms.forms import LoginForm, RegisterForm
auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    current_app.logger.info(f"Dostęp do trasy logowania. Metoda: {request.method}")

    if request.method == 'POST':
        current_app.logger.info("Otrzymano żądanie POST dla logowania")
        current_app.logger.debug(f"Dane formularza: {request.form}")

        if form.validate_on_submit():
            current_app.logger.info(f"Formularz zwalidowany dla nazwy użytkownika: {form.username.data}")
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                current_app.logger.info(f"Użytkownik {user.username} zalogowany pomyślnie")
                flash('Zalogowano pomyślnie.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('page.home'))
            else:
                current_app.logger.warning(f"Nieudana próba logowania dla nazwy użytkownika: {form.username.data}")
                flash('Nieprawidłowa nazwa użytkownika lub hasło.', 'error')
        else:
            current_app.logger.warning(f"Walidacja formularza nie powiodła się: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field.capitalize()}: {error}", 'error')
    else:
        current_app.logger.info("Otrzymano żądanie GET dla formularza logowania")

    return render_template('auth/login.html', form=form)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    current_app.logger.info(f"Dostęp do trasy rejestracji. Metoda: {request.method}")

    if request.method == 'POST':
        current_app.logger.info("Otrzymano żądanie POST dla rejestracji")
        current_app.logger.debug(f"Dane formularza: {request.form}")

        if form.validate_on_submit():
            current_app.logger.info(f"Formularz zwalidowany dla nazwy użytkownika: {form.username.data}")

            # Sprawdzenie, czy nazwa użytkownika już istnieje
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user:
                current_app.logger.warning(f"Próba rejestracji istniejącej nazwy użytkownika: {form.username.data}")
                flash('Nazwa użytkownika już istnieje. Proszę wybrać inną.', 'error')
                return render_template('auth/register.html', form=form)

            # Sprawdzenie, czy adres email już istnieje
            existing_email = User.query.filter_by(email=form.email.data).first()
            if existing_email:
                current_app.logger.warning(f"Próba rejestracji istniejącego adresu email: {form.email.data}")
                flash('Adres email jest już używany. Proszę użyć innego adresu.', 'error')
                return render_template('auth/register.html', form=form)

            # Tworzenie nowego użytkownika
            user = User(
                username=form.username.data,
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data
            )
            user.set_password(form.password.data)
            db.session.add(user)

            try:
                db.session.commit()
                current_app.logger.info(f"Użytkownik {user.username} zarejestrowany pomyślnie")
                flash('Rejestracja zakończona sukcesem. Proszę się zalogować.', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                current_app.logger.error(f"Błąd podczas rejestracji: {str(e)}", exc_info=True)
                db.session.rollback()
                flash('Wystąpił błąd podczas rejestracji. Proszę spróbować ponownie.', 'error')
        else:
            current_app.logger.warning(f"Walidacja formularza nie powiodła się: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field.capitalize()}: {error}", 'error')
    else:
        current_app.logger.info("Otrzymano żądanie GET dla formularza rejestracji")

    return render_template('auth/register.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Zostałeś wylogowany.', 'info')
    return redirect(url_for('page.home'))