from operator import or_

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from calendarproject.models.appointment import Appointment
from calendarproject.extensions import db
from dateutil import parser
from datetime import datetime, timedelta
import pytz

from calendarproject.models.notification import Notification
from calendarproject.utils.notifications import notify_instructor_new_appointment
import json

calendar = Blueprint('calendar', __name__)


@calendar.route('/view')
@login_required
def view():
    if current_user.is_instructor or current_user.is_admin:
        flash('Odmowa dostępu. Musisz być studentem, aby zobaczyć tę stronę.', 'error')
        return redirect(url_for('page.home'))
    return render_template('calendar/view.html')


@calendar.route('/calendar/get_appointments')
@login_required
def get_appointments():
    if current_user.is_instructor or current_user.is_admin:
        flash('Odmowa dostępu. Musisz być studentem, aby zobaczyć tę stronę.', 'error')
        return redirect(url_for('page.home'))

    # Pobierz parametry zapytania
    start_str = request.args.get('start', type=str)
    end_str = request.args.get('end', type=str)
    tz_str = request.args.get('timeZone', type=str, default='UTC')
    instructor_id = request.args.get('instructor_id', type=int)

    try:
        # Parsowanie strefy czasowej
        try:
            tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            return jsonify({'status': 'error', 'message': 'Nieznana strefa czasowa'}), 400

        # Parsowanie start i end
        start = parser.isoparse(start_str)
        end = parser.isoparse(end_str)

        # Lokalizacja dat, jeśli są "naiwne"
        if start.tzinfo is None:
            start = tz.localize(start)
        else:
            start = start.astimezone(tz)

        if end.tzinfo is None:
            end = tz.localize(end)
        else:
            end = end.astimezone(tz)

        # Konwersja na UTC, zakładając, że baza danych przechowuje czasy w UTC
        start_utc = start.astimezone(pytz.UTC)
        end_utc = end.astimezone(pytz.UTC)

        # Przygotowanie zapytania bazowego
        query = Appointment.query.filter(
            Appointment.start_time >= start_utc,
            Appointment.start_time <= end_utc
        )

        # Dodanie filtra instruktora, jeśli podano instructor_id
        if instructor_id:
            query = query.filter(Appointment.instructor_id == instructor_id)

        # Filtrowanie terminów: dostępne lub zarezerwowane przez bieżącego użytkownika
        query = query.filter(
            or_(
                Appointment.is_available == True,
                Appointment.student_id == current_user.id
            )
        )

        appointments = query.all()

        # Przygotowanie wydarzeń do zwrócenia
        events = []
        for appointment in appointments:
            if appointment.is_available:
                title = 'Dostępny'
                color = '#1B8359'
            elif appointment.student_id == current_user.id and appointment.status != 'confirmed':
                title = f'Temat konsultacji: {appointment.topic}'
                color = '#996C00'
            elif appointment.student_id == current_user.id and appointment.status == 'confirmed':
                title = f'Temat konsultacji: {appointment.topic}'
                color = '#9C27B0'
            else:
                continue  # Pomijanie terminów zarezerwowanych przez innych uczniów

            events.append({
                'id': appointment.id,
                'titleMessage': title,
                'title': '',
                'start': appointment.start_time.isoformat(),
                'end': appointment.end_time.isoformat(),
                'color': color,
            })

        return jsonify(events)

    except Exception as e:
        current_app.logger.error(f"Błąd w get_appointments: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Nieprawidłowe żądanie'}), 400


@calendar.route('/calendar/book/<int:appointment_id>', methods=['POST'])
@login_required
def book(appointment_id):
    if current_user.is_instructor or current_user.is_admin:
        flash('Odmowa dostępu. Musisz być studentem, aby zobaczyć tę stronę.', 'error')
        return redirect(url_for('page.home'))

    appointment = Appointment.query.get_or_404(appointment_id)
    current_time = datetime.utcnow()
    appointment_time = appointment.start_time

    # Sprawdzenie, czy termin jest więcej niż 30 minut od teraz
    if appointment_time - current_time <= timedelta(minutes=30):
        current_app.logger.warning(f"Próba rezerwacji terminu mniej niż 30 minut od teraz: ID {appointment_id}")
        return jsonify(
            {'status': 'error', 'message': 'Nie można rezerwować terminów mniej niż 30 minut od teraz.'}), 400

    if not appointment.is_available:
        return jsonify({'status': 'error', 'message': 'Ten termin jest już zarezerwowany.'}), 400

    data = json.loads(request.data)
    topic = data.get('topic', '')

    appointment.student_id = current_user.id
    appointment.is_available = False
    appointment.status = 'pending'
    appointment.topic = topic

    try:
        db.session.commit()
        notify_instructor_new_appointment(appointment.instructor, appointment)
        notification = Notification(
            user_id=appointment.instructor_id,
            message=f'Nowa wizyta do zaakceptowania na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} od {current_user.first_name + " " + current_user.last_name} na temat: ' + appointment.topic + '.',
            type='appointment',
            related_id=appointment.id
        )
        db.session.add(notification)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Termin został pomyślnie zarezerwowany!'})
    except Exception as e:
        print(current_app.config['MAIL_USERNAME'])
        current_app.logger.error(f"Błąd podczas rezerwacji terminu: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify(
            {'status': 'error', 'message': 'Wystąpił błąd podczas rezerwacji terminu. Proszę spróbować ponownie.'}), 500


@calendar.route('/calendar/cancel/<int:appointment_id>', methods=['POST'])
@login_required
def cancel(appointment_id):
    if current_user.is_instructor or current_user.is_admin:
        flash('Odmowa dostępu. Nie możesz być instruktorem, aby zobaczyć tę stronę.', 'error')
        return redirect(url_for('page.home'))

    appointment = Appointment.query.get_or_404(appointment_id)
    current_time = datetime.utcnow()
    appointment_time = appointment.start_time

    # Sprawdzenie, czy termin jest więcej niż 30 minut od teraz
    if appointment_time - current_time <= timedelta(minutes=30):
        current_app.logger.warning(f"Próba anulowania terminu mniej niż 30 minut od teraz: ID {appointment_id}")
        return jsonify({'status': 'error', 'message': 'Nie można anulować terminów mniej niż 30 minut od teraz.'}), 400

    if appointment.student_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Możesz anulować tylko swoje własne terminy.'}), 403

    try:
        appointment.is_available = True
        appointment.student_id = None
        appointment.status = 'available'
        appointment.topic = None
        notification = Notification(
            user_id=appointment.instructor_id,
            message=f'Wizyta na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} została anulowana przez studenta {current_user.first_name + " " + current_user.last_name}.',
            type="appointment",
            related_id=appointment.id
        )
        db.session.add(notification)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Twoja rezerwacja została anulowana.'})
    except Exception as e:
        current_app.logger.error(f"Błąd podczas anulowania terminu: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error',
                        'message': 'Wystąpił błąd podczas anulowania rezerwacji. Proszę spróbować ponownie.'}), 500
