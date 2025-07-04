from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from dateutil import parser
import pytz
from sqlalchemy.orm import joinedload
from datetime import time
from datetime import datetime, timedelta, timezone
from calendarproject.models.appointment import Appointment
from calendarproject.extensions import db
from sqlalchemy import cast, DateTime, func
from datetime import datetime, timedelta
from calendarproject.models.user import User
import json

from calendarproject.models.notification import Notification

instructor = Blueprint('instructor', __name__)


@instructor.route('/api/instructors', methods=['GET'])
@login_required
def get_instructors():
    current_app.logger.info(f"Dostęp do /api/instructors. Metoda: {request.method}")
    try:
        instructors = User.query.filter_by(is_instructor=True, deleted=False).all()
        instructors_data = [{
            'id': instructor.id,
            'first_name': instructor.first_name,
            'last_name': instructor.last_name,
            'full_name': f"{instructor.first_name} {instructor.last_name}"
        } for instructor in instructors]

        current_app.logger.info(f"Znaleziono {len(instructors_data)} instruktorów.")
        return jsonify(instructors_data)
    except Exception as e:
        current_app.logger.error(f"Błąd podczas pobierania instruktorów: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Wystąpił błąd podczas pobierania instruktorów.'}), 500


@instructor.route('/instructor/calendar')
@login_required
def calendar():
    current_app.logger.info(f"Dostęp do /instructor/calendar. Metoda: {request.method}")
    if not current_user.is_instructor:
        current_app.logger.warning(
            f"Próba dostępu do kalendarza instruktora przez nieuprawnionego użytkownika: {current_user.id}")
        flash('Dostęp zabroniony. Musisz być instruktorem, aby wyświetlić tę stronę.', 'error')
        return redirect(url_for('page.home'))
    return render_template('instructor/calendar.html')


@instructor.route('/instructor/get_appointments', methods=['GET'])
@login_required
def get_appointments():
    current_app.logger.info(f"Dostęp do /instructor/get_appointments. Metoda: {request.method}")
    if not current_user.is_instructor:
        current_app.logger.warning(
            f"Próba pobrania terminów instruktora przez nieuprawnionego użytkownika: {current_user.id}")
        return jsonify([])

    # Pobierz parametry zapytania
    start_str = request.args.get('start', type=str)
    end_str = request.args.get('end', type=str)
    tz_str = request.args.get('timeZone', type=str, default='UTC')

    current_app.logger.debug(f"Parametry zapytania: start={start_str}, end={end_str}, timeZone={tz_str}")

    try:
        # Parsowanie strefy czasowej
        try:
            tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            current_app.logger.warning(f"Nieznana strefa czasowa: {tz_str}")
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

        # Filtrowanie terminów z joinedload dla studenta
        appointments = Appointment.query.options(joinedload(Appointment.student)).filter(
            Appointment.instructor_id == current_user.id,
            Appointment.start_time >= start_utc,
            Appointment.start_time <= end_utc
        ).all()

        current_app.logger.debug(f"Znaleziono {len(appointments)} terminów w zadanym okresie.")

        # Przygotowanie wydarzeń do zwrócenia
        events = []
        for appointment in appointments:
            student_name = f"{appointment.student.first_name} {appointment.student.last_name}" if appointment.student else ""
            events.append({
                'id': appointment.id,
                'titleMessage': 'Dostępny' if appointment.is_available else f'Temat konsultacji: {appointment.topic}',
                'title': '',
                'student': student_name,
                'is_available': appointment.is_available,
                'start': appointment.start_time.isoformat(),
                'end': appointment.end_time.isoformat(),
                'color': '#1B8359' if appointment.is_available else ('#996C00' if appointment.status == 'pending' else '#9C27B0'),
                'status': appointment.status
            })

        return jsonify(events)

    except Exception as e:
        current_app.logger.error(f"Błąd w get_appointments: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Nieprawidłowe żądanie'}), 400


@instructor.route('/instructor/add_appointment', methods=['POST'])
@login_required
def add_appointment():
    current_app.logger.info(f"Dostęp do /instructor/add_appointment. Metoda: {request.method}")
    if not current_user.is_instructor:
        current_app.logger.warning(f"Próba dodania terminu przez nieuprawnionego użytkownika: {current_user.id}")
        return jsonify({'status': 'error', 'message': 'Odmowa dostępu'}), 403

    try:
        data = json.loads(request.data)
        current_app.logger.debug(f"Otrzymane dane: {data}")

        start_time = datetime.fromisoformat(data['start'])
        end_time = datetime.fromisoformat(data['end'])

        current_app.logger.debug(f"Parsowane daty: start={start_time}, end={end_time}")

        # Upewnij się, że daty zawierają informację o strefie czasowej
        if start_time.tzinfo is None or end_time.tzinfo is None:
            current_app.logger.warning("Nieprawidłowy format daty. Brak informacji o strefie czasowej.")
            return jsonify(
                {'status': 'error', 'message': 'Nieprawidłowy format daty. Brak informacji o strefie czasowej.'}), 400

        # Oblicz aktualny czas w tej samej strefie czasowej co start_time
        now = datetime.now(timezone.utc).astimezone(start_time.tzinfo)

        # Sprawdź czy start_time jest co najmniej godzinę w przyszłości
        if start_time < now + timedelta(hours=1):
            current_app.logger.warning("Termin musi być co najmniej godzinę do przodu od obecnego czasu.")
            return jsonify(
                {'status': 'error', 'message': 'Termin musi być co najmniej godzinę do przodu od obecnego czasu.'}), 400

        # Sprawdź czy end_time jest po start_time
        if end_time <= start_time:
            current_app.logger.warning("Czas zakończenia musi być po czasie rozpoczęcia.")
            return jsonify({'status': 'error', 'message': 'Czas zakończenia musi być po czasie rozpoczęcia.'}), 400

        # Sprawdź czy to termin całodniowy
        is_full_day = start_time.time() == time(0, 0) and end_time.time() == time(23, 59, 59)

        if is_full_day:
            # Sprawdź, czy istnieją już terminy na ten dzień
            existing_appointments = Appointment.query.filter(
                Appointment.instructor_id == current_user.id,
                func.date(Appointment.start_time) == start_time.date()
            ).first()

            if existing_appointments:
                current_app.logger.warning(
                    "Nie można dodać całodniowego terminu, ponieważ istnieją już terminy w tym dniu.")
                return jsonify({'status': 'error',
                                'message': 'Nie można dodać całodniowego terminu, ponieważ istnieją już terminy w tym dniu.'}), 400

        new_appointment = Appointment(
            instructor_id=current_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        db.session.add(new_appointment)
        db.session.commit()
        current_app.logger.info(f"Dodano nowy termin. ID: {new_appointment.id}")
        return jsonify({'status': 'success', 'id': new_appointment.id}), 201

    except json.JSONDecodeError:
        current_app.logger.error("Nieprawidłowe dane JSON.", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Nieprawidłowe dane JSON.'}), 400
    except KeyError as e:
        current_app.logger.error(f"Brakujący klucz: {e.args[0]}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Brakujący klucz: {e.args[0]}'}), 400
    except ValueError as e:
        current_app.logger.error(f"Nieprawidłowy format daty: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Nieprawidłowy format daty: {str(e)}'}), 400
    except Exception as e:
        current_app.logger.error(f"Wystąpił nieoczekiwany błąd: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Wystąpił nieoczekiwany błąd.'}), 500


@instructor.route('/instructor/delete_appointment', methods=['POST'])
@login_required
def delete_appointment():
    current_app.logger.info(f"Dostęp do /instructor/delete_appointment. Metoda: {request.method}")
    if not current_user.is_instructor:
        current_app.logger.warning(f"Próba usunięcia terminu przez nieuprawnionego użytkownika: {current_user.id}")
        return jsonify({'status': 'error', 'message': 'Odmowa dostępu'}), 403

    try:
        data = json.loads(request.data)
        appointment_id = data['id']
        current_app.logger.debug(f"Próba usunięcia terminu o ID: {appointment_id}")

        appointment = Appointment.query.get(appointment_id)
        if appointment and appointment.instructor_id == current_user.id and appointment.is_available:
            db.session.delete(appointment)
            db.session.commit()
            current_app.logger.info(f"Usunięto termin o ID: {appointment_id}")
            return jsonify({'status': 'success'})
        else:
            if not appointment:
                current_app.logger.warning(f"Termin o ID {appointment_id} nie został znaleziony.")
            elif appointment.instructor_id != current_user.id:
                current_app.logger.warning(f"Próba usunięcia terminu innego instruktora. Termin ID: {appointment_id}")
            elif not appointment.is_available:
                current_app.logger.warning(f"Próba usunięcia niedostępnego terminu. Termin ID: {appointment_id}")

            return jsonify({'status': 'error', 'message': 'Termin nie został znaleziony lub nie jest dostępny'}), 404
    except Exception as e:
        current_app.logger.error(f"Wystąpił błąd podczas usuwania terminu: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Wystąpił błąd podczas usuwania terminu.'}), 500


@instructor.route('/instructor/confirm_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def confirm_appointment(appointment_id):
    current_app.logger.info(f"Dostęp do /instructor/confirm_appointment/{appointment_id}. Metoda: {request.method}")
    if not current_user.is_instructor:
        current_app.logger.warning(f"Próba potwierdzenia terminu przez nieuprawnionego użytkownika: {current_user.id}")
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.instructor_id != current_user.id:
            current_app.logger.warning(f"Próba potwierdzenia terminu innego instruktora. Termin ID: {appointment_id}")
            return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

        if appointment.status != 'pending':
            current_app.logger.warning(
                f"Próba potwierdzenia terminu o statusie innym niż 'pending'. Status: {appointment.status}")
            return jsonify({'status': 'error', 'message': 'Wizyta została już zaakceptowana'}), 403

        appointment.status = 'confirmed'
        db.session.commit()

        instructor_name = f"{current_user.first_name} {current_user.last_name}"
        notification = Notification(
            user_id=appointment.student_id,
            message=f'Twoja wizyta na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} u {instructor_name} została zaakceptowana.',
            type="appointment",
            related_id=appointment.id
        )
        db.session.add(notification)
        db.session.commit()

        current_app.logger.info(f"Zaakceptowano termin o ID: {appointment_id}")
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.error(f"Wystąpił błąd podczas potwierdzania terminu: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Wystąpił błąd podczas potwierdzania terminu.'}), 500


@instructor.route('/instructor/cancel_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    current_app.logger.info(f"Dostęp do /instructor/cancel_appointment/{appointment_id}. Metoda: {request.method}")
    if not current_user.is_instructor:
        current_app.logger.warning(f"Próba anulowania terminu przez nieuprawnionego użytkownika: {current_user.id}")
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.instructor_id != current_user.id:
            current_app.logger.warning(f"Próba anulowania terminu innego instruktora. Termin ID: {appointment_id}")
            return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

        if appointment.status != 'confirmed':
            current_app.logger.warning(
                f"Próba anulowania terminu o statusie innym niż 'confirmed'. Status: {appointment.status}")
            return jsonify({'status': 'error', 'message': 'Wizyta została już anulowana'}), 403

        student_id = appointment.student_id  # Zapisz ID studenta przed jego usunięciem

        appointment.status = 'pending'
        appointment.student_id = None
        appointment.topic = None
        appointment.is_available = True
        db.session.commit()

        instructor_name = f"{current_user.first_name} {current_user.last_name}"
        notification = Notification(
            user_id=student_id,
            message=f'Twoja wizyta na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} u {instructor_name} została anulowana.',
            type="appointment",
            related_id=appointment.id
        )
        db.session.add(notification)
        db.session.commit()

        current_app.logger.info(f"Anulowano termin o ID: {appointment_id}")
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.error(f"Wystąpił błąd podczas anulowania terminu: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Wystąpił błąd podczas anulowania terminu.'}), 500


@instructor.route('/instructor/reject_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def reject_appointment(appointment_id):
    current_app.logger.info(f"Dostęp do /instructor/reject_appointment/{appointment_id}. Metoda: {request.method}")
    if not current_user.is_instructor:
        current_app.logger.warning(f"Próba odrzucenia terminu przez nieuprawnionego użytkownika: {current_user.id}")
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.instructor_id != current_user.id:
            current_app.logger.warning(f"Próba odrzucenia terminu innego instruktora. Termin ID: {appointment_id}")
            return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

        student_id = appointment.student_id  # Zapisz ID studenta przed jego usunięciem

        # Tworzenie notyfikacji dla studenta
        instructor_name = f"{current_user.first_name} {current_user.last_name}"
        notification = Notification(
            user_id=student_id,
            message=f'Twoja wizyta na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} u {instructor_name} została odrzucona.',
            type="appointment",
            related_id=appointment.id
        )

        appointment.status = 'rejected'
        appointment.is_available = True
        appointment.student_id = None
        appointment.topic = None
        db.session.commit()

        db.session.add(notification)
        db.session.commit()

        current_app.logger.info(f"Odrzucono termin o ID: {appointment_id}")
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.error(f"Wystąpił błąd podczas odrzucania terminu: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Wystąpił błąd podczas odrzucania terminu.'}), 500
