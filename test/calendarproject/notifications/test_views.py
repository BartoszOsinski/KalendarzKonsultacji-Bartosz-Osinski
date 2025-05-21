import pytest
import json
from datetime import datetime, timedelta
import pytz
from calendarproject.models.user import User
from calendarproject.models.appointment import Appointment
from calendarproject.models.notification import Notification
from calendarproject.extensions import db

class TestNotificationViews:
    """Test suite for notification functionality."""

    @pytest.fixture
    def student_user(self, db):
        """Create a student user for testing."""
        student = User(
            username='student',
            email='student@example.com',
            first_name='Student',
            last_name='User',
            is_instructor=False,
            is_admin=False
        )
        student.set_password('password')
        db.session.add(student)
        db.session.commit()
        return student

    @pytest.fixture
    def instructor_user(self, db):
        """Create an instructor user for testing."""
        instructor = User(
            username='instructor',
            email='instructor@example.com',
            first_name='Test',
            last_name='Instructor',
            is_instructor=True
        )
        instructor.set_password('password')
        db.session.add(instructor)
        db.session.commit()
        return instructor

    @pytest.fixture
    def appointment(self, db, instructor_user, student_user):
        """Create an appointment for testing notifications."""
        start_time = datetime.now(pytz.UTC) + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        appointment = Appointment(
            instructor_id=instructor_user.id,
            student_id=student_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=False,
            topic='Test topic',
            status='confirmed'
        )
        db.session.add(appointment)
        db.session.commit()
        return appointment

    @pytest.fixture
    def notification(self, db, student_user, appointment):
        """Create a notification for testing."""
        notification = Notification(
            user_id=student_user.id,
            message='Test notification message',
            type='appointment',
            related_id=appointment.id,
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    def login(self, client, username, password):
        """Helper function to login a user."""
        return client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_get_notifications(self, client, student_user, notification):
        """Test getting user notifications."""
        self.login(client, 'student', 'password')

        response = client.get('/api/notifications')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'unread_count' in data
        assert data['unread_count'] == 1
        assert 'notifications' in data
        assert len(data['notifications']) == 1

        # Check notification data
        notification_data = data['notifications'][0]
        assert notification_data['id'] == notification.id
        assert notification_data['message'] == 'Test notification message'
        assert notification_data['is_read'] is False
        assert notification_data['type'] == 'appointment'
        assert notification_data['related_id'] == notification.related_id

    def test_get_notification_details(self, client, student_user, notification, appointment):
        """Test getting detailed information about a notification."""
        self.login(client, 'student', 'password')

        response = client.get(f'/api/notifications/{notification.id}/details')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'appointment' in data

        # Check appointment data
        appointment_data = data['appointment']
        assert appointment_data['id'] == appointment.id
        assert 'Test topic' in appointment_data['title']
        assert appointment_data['start'] == appointment.start_time.isoformat()
        assert appointment_data['end'] == appointment.end_time.isoformat()
        assert 'extendedProps' in appointment_data
        assert 'status' in appointment_data['extendedProps']
        assert appointment_data['extendedProps']['status'] == 'confirmed'

    def test_get_notification_details_unauthorized(self, client, db, student_user, instructor_user, notification):
        """Test that users cannot access other users' notification details."""
        # Create another user
        other_user = User(
            username='otheruser',
            email='other@example.com',
            first_name='Other',
            last_name='User'
        )
        other_user.set_password('password')
        db.session.add(other_user)
        db.session.commit()

        # Login as other user
        self.login(client, 'otheruser', 'password')

        # Try to get notification details for notification that belongs to student
        response = client.get(f'/api/notifications/{notification.id}/details')

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Unauthorized' in data['message']

    def test_mark_notification_as_read(self, client, student_user, notification):
        """Test marking a notification as read."""
        self.login(client, 'student', 'password')

        response = client.post(f'/api/notifications/{notification.id}/read')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'

        # Verify notification is marked as read in DB
        updated_notification = Notification.query.get(notification.id)
        assert updated_notification.is_read is True

    def test_delete_notification(self, client, student_user, notification):
        """Test deleting a notification."""
        self.login(client, 'student', 'password')

        response = client.delete(f'/api/notifications/{notification.id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'

        # Verify notification is deleted from DB
        deleted_notification = Notification.query.get(notification.id)
        assert deleted_notification is None

    def test_delete_notification_unauthorized(self, client, db, student_user, notification):
        """Test that users cannot delete other users' notifications."""
        # Create another user
        other_user = User(
            username='otheruser',
            email='other@example.com',
            first_name='Other',
            last_name='User'
        )
        other_user.set_password('password')
        db.session.add(other_user)
        db.session.commit()

        # Login as other user
        self.login(client, 'otheruser', 'password')

        # Try to delete notification that belongs to student
        response = client.delete(f'/api/notifications/{notification.id}')

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Unauthorized' in data['message']

        # Verify notification still exists
        existing_notification = Notification.query.get(notification.id)
        assert existing_notification is not None

    def test_get_notifications_multiple(self, client, db, student_user, appointment):
        """Test getting multiple notifications with correct ordering."""
        # Create multiple notifications
        for i in range(3):
            notification = Notification(
                user_id=student_user.id,
                message=f'Test notification {i}',
                type='appointment',
                related_id=appointment.id,
                is_read=False
            )
            db.session.add(notification)
            db.session.commit()

        self.login(client, 'student', 'password')

        response = client.get('/api/notifications')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['unread_count'] == 3
        assert len(data['notifications']) <= 5  # API should return at most 5 notifications

        # Verify notifications are returned in descending order by timestamp
        timestamps = [n['timestamp'] for n in data['notifications']]
        assert timestamps == sorted(timestamps, reverse=True)