import pytest
import json
from datetime import datetime, timedelta
import pytz
from calendarproject.models.user import User
from calendarproject.models.appointment import Appointment
from calendarproject.models.notification import Notification
from calendarproject.extensions import db
from flask_login import current_user

class TestInstructorViews:
    """Test suite for instructor functionality."""

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
    def available_appointment(self, db, instructor_user):
        """Create an available appointment for testing."""
        # Set appointment time to future date
        start_time = datetime.now(pytz.UTC) + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        appointment = Appointment(
            instructor_id=instructor_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        db.session.add(appointment)
        db.session.commit()
        return appointment

    @pytest.fixture
    def pending_appointment(self, db, instructor_user, student_user):
        """Create a pending appointment for testing."""
        # Set appointment time to future date
        start_time = datetime.now(pytz.UTC) + timedelta(days=2)
        end_time = start_time + timedelta(hours=1)

        appointment = Appointment(
            instructor_id=instructor_user.id,
            student_id=student_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=False,
            topic='Pending appointment',
            status='pending'
        )
        db.session.add(appointment)
        db.session.commit()
        return appointment

    def login(self, client, username, password):
        """Helper function to login a user."""
        return client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_get_instructors(self, client, instructor_user, student_user):
        """Test getting the list of instructors."""
        # Make sure the student user exists in the DB before trying to login
        assert student_user is not None
        assert student_user.id is not None

        # Login with the student user - ensure we're clearing any previous session
        with client.session_transaction() as sess:
            if '_user_id' in sess:
                del sess['_user_id']

        login_response = client.post('/login', data={
            'username': 'student',
            'password': 'password'
        }, follow_redirects=True)

        # Verify login worked
        assert login_response.status_code == 200

        # Make request to get instructors endpoint
        response = client.get('/api/instructors')

        # If we get a redirect, follow it (in case auth is needed)
        if response.status_code == 302:
            response = client.get(response.location)

        assert response.status_code == 200
        instructors = json.loads(response.data)

        # Check instructor data is in the response
        assert len(instructors) > 0
        assert any(i['id'] == instructor_user.id for i in instructors)

    def test_instructor_calendar_access(self, client, instructor_user, student_user):
        """Test that only instructors can access the instructor calendar."""
        # Login as instructor
        self.login(client, 'instructor', 'password')
        response = client.get('/instructor/calendar')
        assert response.status_code == 200

        # Login as student
        client.get('/logout')
        self.login(client, 'student', 'password')

        # Try to access instructor calendar - check for redirect without following
        response = client.get('/instructor/calendar', follow_redirects=False)
        assert response.status_code == 302  # Should be redirected

        # Verify redirect location goes to home page
        assert response.location == '/' or response.location.endswith('/home')

    def test_instructor_get_appointments(self, client, instructor_user, available_appointment, pending_appointment):
        """Test getting instructor appointments."""
        self.login(client, 'instructor', 'password')

        # Current date plus/minus 1 month
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
        end_date = (datetime.now() + timedelta(days=30)).isoformat()

        response = client.get(
            f'/instructor/get_appointments?start={start_date}&end={end_date}&timeZone=UTC'
        )

        assert response.status_code == 200
        appointments = json.loads(response.data)
        assert len(appointments) == 2  # Both available and pending appointments

        # Check appointment data for available appointment
        available_appt = next(a for a in appointments if a['id'] == available_appointment.id)
        assert available_appt['is_available'] is True
        assert available_appt['color'] == '#1B8359'  # Green for available

        # Check appointment data for pending appointment
        pending_appt = next(a for a in appointments if a['id'] == pending_appointment.id)
        assert pending_appt['is_available'] is False
        assert pending_appt['status'] == 'pending'
        assert pending_appt['color'] == '#996C00'  # Yellow for pending
        assert 'Pending appointment' in pending_appt['titleMessage']

    def test_add_appointment_success(self, client, instructor_user):
        """Test successfully adding a new appointment slot."""
        self.login(client, 'instructor', 'password')

        # Create appointment data 2 days from now
        start_time = (datetime.now(pytz.UTC) + timedelta(days=2)).isoformat()
        end_time = (datetime.now(pytz.UTC) + timedelta(days=2, hours=1)).isoformat()

        appointment_data = {
            'start': start_time,
            'end': end_time
        }

        response = client.post(
            '/instructor/add_appointment',
            data=json.dumps(appointment_data),
            content_type='application/json'
        )

        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify appointment was created
        appointment = Appointment.query.get(response_data['id'])
        assert appointment is not None
        assert appointment.instructor_id == instructor_user.id
        assert appointment.is_available is True

        # Compare timestamps ignoring timezone info differences in formatting
        # Extract just the datetime part without timezone info
        created_time = appointment.start_time.strftime('%Y-%m-%dT%H:%M:%S')
        expected_time = datetime.fromisoformat(start_time.replace('Z', '+00:00')).strftime('%Y-%m-%dT%H:%M:%S')
        assert created_time == expected_time

    def test_add_appointment_invalid_time(self, client, instructor_user):
        """Test adding appointment with invalid time (too soon)."""
        self.login(client, 'instructor', 'password')

        # Create appointment data 30 minutes from now (less than 1 hour requirement)
        start_time = (datetime.now(pytz.UTC) + timedelta(minutes=30)).isoformat()
        end_time = (datetime.now(pytz.UTC) + timedelta(minutes=90)).isoformat()

        appointment_data = {
            'start': start_time,
            'end': end_time
        }

        response = client.post(
            '/instructor/add_appointment',
            data=json.dumps(appointment_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert 'godzinę do przodu' in response_data['message']

    def test_delete_appointment_success(self, client, instructor_user, available_appointment):
        """Test successfully deleting an available appointment."""
        self.login(client, 'instructor', 'password')

        delete_data = {
            'id': available_appointment.id
        }

        response = client.post(
            '/instructor/delete_appointment',
            data=json.dumps(delete_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify appointment was deleted
        appointment = Appointment.query.get(available_appointment.id)
        assert appointment is None

    def test_delete_appointment_booked(self, client, instructor_user, pending_appointment):
        """Test that booked appointments cannot be deleted."""
        self.login(client, 'instructor', 'password')

        delete_data = {
            'id': pending_appointment.id
        }

        response = client.post(
            '/instructor/delete_appointment',
            data=json.dumps(delete_data),
            content_type='application/json'
        )

        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert 'nie jest dostępny' in response_data['message']

        # Verify appointment was not deleted
        appointment = Appointment.query.get(pending_appointment.id)
        assert appointment is not None

    def test_confirm_appointment(self, client, instructor_user, pending_appointment):
        """Test confirming a pending appointment."""
        self.login(client, 'instructor', 'password')

        response = client.post(f'/instructor/confirm_appointment/{pending_appointment.id}')

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify appointment was updated
        appointment = Appointment.query.get(pending_appointment.id)
        assert appointment.status == 'confirmed'

        # Verify notification was created
        notification = Notification.query.filter_by(
            user_id=pending_appointment.student_id,
            related_id=pending_appointment.id
        ).first()
        assert notification is not None
        assert notification.type == 'appointment'
        assert 'zaakceptowana' in notification.message

    def test_reject_appointment(self, client, instructor_user, pending_appointment):
        """Test rejecting a pending appointment."""
        self.login(client, 'instructor', 'password')

        response = client.post(f'/instructor/reject_appointment/{pending_appointment.id}')

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify appointment was updated
        appointment = Appointment.query.get(pending_appointment.id)
        assert appointment.status == 'rejected'
        assert appointment.is_available is True
        assert appointment.student_id is None
        assert appointment.topic is None

        # Verify notification was created
        notification = Notification.query.filter_by(
            type='appointment',
            related_id=pending_appointment.id
        ).first()
        assert notification is not None
        assert 'odrzucona' in notification.message

    def test_cancel_confirmed_appointment(self, client, db, instructor_user, student_user):
        """Test canceling a confirmed appointment."""
        # Create a confirmed appointment
        start_time = datetime.now(pytz.UTC) + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        confirmed_appointment = Appointment(
            instructor_id=instructor_user.id,
            student_id=student_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=False,
            topic='Confirmed appointment',
            status='confirmed'
        )
        db.session.add(confirmed_appointment)
        db.session.commit()

        # Login as instructor
        self.login(client, 'instructor', 'password')

        # Cancel appointment
        response = client.post(f'/instructor/cancel_appointment/{confirmed_appointment.id}')

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify appointment was updated
        appointment = Appointment.query.get(confirmed_appointment.id)
        assert appointment.status == 'pending'
        assert appointment.is_available is True
        assert appointment.student_id is None
        assert appointment.topic is None

        # Verify notification was created
        notification = Notification.query.filter_by(
            user_id=student_user.id,
            related_id=confirmed_appointment.id
        ).first()
        assert notification is not None
        assert 'anulowana' in notification.message