from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from calendarproject.models.appointment import Appointment
from calendarproject.models.user import User
from calendarproject.extensions import db
from calendarproject.forms.forms import CreateInstructorForm
from calendarproject.models.notification import Notification
import traceback

admin = Blueprint('admin', __name__)

@admin.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin to view this page.', 'error')
        return redirect(url_for('page.home'))

    # Fetch appointments for the current instructor
    appointments = Appointment.query.filter_by(instructor_id=current_user.id).all()

    # Separate booked and available appointments
    booked_appointments = [apt for apt in appointments if not apt.is_available]
    available_appointments = [apt for apt in appointments if apt.is_available]

    # Get instructors for the instructor list
    instructors = User.query.filter_by(is_instructor=True, deleted=False).all()

    # Form for adding a new instructor
    form = CreateInstructorForm()

    return render_template('admin/dashboard.html',
                           booked_appointments=booked_appointments,
                           available_appointments=available_appointments,
                           instructors=instructors,
                           form=form)


@admin.route('/admin/delete_instructor/<int:instructor_id>', methods=['POST'])
@login_required
def delete_instructor(instructor_id):
    current_app.logger.info(f"Dostęp do /admin/delete_instructor/{instructor_id}. Metoda: {request.method}")

    # Sprawdzenie czy użytkownik jest administratorem
    if not current_user.is_admin:
        current_app.logger.warning(f"Próba usunięcia instruktora przez nieuprawnionego użytkownika: {current_user.id}")
        return jsonify(
            {'status': 'error', 'message': 'Odmowa dostępu. Tylko administrator może usunąć instruktora.'}), 403

    try:
        # Pobierz instruktora
        instructor_to_delete = User.query.get_or_404(instructor_id)

        # Sprawdź czy użytkownik jest rzeczywiście instruktorem
        if not instructor_to_delete.is_instructor:
            current_app.logger.warning(
                f"Próba usunięcia użytkownika, który nie jest instruktorem. User ID: {instructor_id}")
            return jsonify({'status': 'error', 'message': 'Wskazany użytkownik nie jest instruktorem.'}), 400

        instructor_name = f"{instructor_to_delete.first_name} {instructor_to_delete.last_name}"
        current_app.logger.info(f"Przygotowanie do usunięcia instruktora: {instructor_name} (ID: {instructor_id})")

        # Pobierz tylko zarezerwowane terminy instruktora, aby poinformować studentów
        booked_appointments = Appointment.query.filter(
            Appointment.instructor_id == instructor_id,
            Appointment.is_available == False
        ).all()

        current_app.logger.info(
            f"Znaleziono {len(booked_appointments)} zarezerwowanych terminów instruktora do powiadomień.")

        # Zbierz unikalne ID studentów do powiadomienia
        student_ids = set()
        for appointment in booked_appointments:
            if appointment.student_id:
                student_ids.add(appointment.student_id)

        # Utwórz powiadomienia dla studentów
        for student_id in student_ids:
            notification = Notification(
                user_id=student_id,
                message=f'Konto instruktora {instructor_name} zostało usunięte, toteż wszystkie terminy spotkań zostały odwołane.',
                type="instructor_deleted",
                related_id=instructor_id
            )
            db.session.add(notification)

        # Usuń wszystkie terminy instruktora (zarówno zarezerwowane jak i dostępne)
        deleted_appointments_count = Appointment.query.filter(
            Appointment.instructor_id == instructor_id
        ).delete()

        current_app.logger.info(f"Usunięto wszystkie ({deleted_appointments_count}) terminy instruktora.")

        # Usuń instruktora
        instructor_to_delete.soft_delete()
        db.session.commit()

        current_app.logger.info(f"Instruktor {instructor_name} (ID: {instructor_id}) został pomyślnie usunięty.")
        return jsonify({
            'status': 'success',
            'message': f'Instruktor {instructor_name} został pomyślnie usunięty wraz z {deleted_appointments_count} terminami.',
            'notified_students': len(student_ids)
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Wystąpił błąd podczas usuwania instruktora: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Wystąpił błąd podczas usuwania instruktora.'}), 500


@admin.route('/create_instructor', methods=['POST'])
@login_required
def create_instructor():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin to perform this action.', 'error')
        return redirect(url_for('page.home'))

    form = CreateInstructorForm()

    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Nazwa użytkownika już istnieje. Proszę wybrać inną.', 'error')
            return redirect(url_for('admin.dashboard'))

        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Adres email jest już używany. Proszę użyć innego adresu.', 'error')
            return redirect(url_for('admin.dashboard'))

        # Create new instructor
        new_instructor = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            is_instructor=True  # Set as instructor
        )
        new_instructor.set_password(form.password.data)

        try:
            db.session.add(new_instructor)
            db.session.commit()
            flash(f'Instruktor {new_instructor.username} został pomyślnie utworzony.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Wystąpił błąd podczas tworzenia instruktora: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field.capitalize()}: {error}", 'error')

    return redirect(url_for('admin.dashboard'))
