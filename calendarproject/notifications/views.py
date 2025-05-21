from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from calendarproject.models.notification import Notification
from calendarproject.models.appointment import Appointment
from calendarproject.extensions import db

notifications = Blueprint('notifications', __name__)


@notifications.route('/api/notifications')
@login_required
def get_notifications():
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    recent_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.timestamp.desc()).limit(5).all()

    notifications_data = [{
        'id': notification.id,
        'message': notification.message,
        'timestamp': notification.timestamp.isoformat(),
        'is_read': notification.is_read,
        'type': notification.type,
        'related_id': notification.related_id
    } for notification in recent_notifications]

    return jsonify({
        'unread_count': unread_count,
        'notifications': notifications_data
    })


@notifications.route('/api/notifications/<int:notification_id>/details', methods=['GET'])
@login_required
def get_notification_details(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    appointment = Appointment.query.get(notification.related_id)
    if appointment:
        # Bezpieczne pobieranie danych studenta
        student_info = ""
        if appointment.student:
            student_info = f"{appointment.student.first_name} {appointment.student.last_name}"

        response = {
            'status': 'success',
            'appointment': {
                'id': appointment.id,
                'start': appointment.start_time.isoformat(),
                'end': appointment.end_time.isoformat(),
                'title': 'Temat konsultacji: ' + str(appointment.topic),
                'extendedProps': {
                    'student': student_info,
                    'status': appointment.status
                }
            }
        }

        if current_user.is_instructor and appointment.status == 'pending':
            response['appointment']['extendedProps']['can_accept'] = True
            response['appointment']['extendedProps']['can_decline'] = True

        return jsonify(response)

    return jsonify({'status': 'error', 'message': 'No details available'}), 404


@notifications.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_as_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    notification.is_read = True
    db.session.commit()
    return jsonify({'status': 'success'})


@notifications.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    db.session.delete(notification)
    db.session.commit()
    return jsonify({'status': 'success'})
