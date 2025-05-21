import pytest
import json
from datetime import datetime, timedelta
import pytz
from calendarproject.models.user import User
from calendarproject.models.appointment import Appointment
from calendarproject.models.notification import Notification
from calendarproject.extensions import db

class TestCalendarViews:
    """Test suite for the calendar views (student functionality)."""

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

    def login(self, client, username, password):
        """Helper function to login a user."""
        return client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_view_calendar_access_student(self, client, student_user):
        """Test that students can access the calendar view page."""
        self.login(client, 'student', 'password')
        response = client.get('/view')
        assert response.status_code == 200

    def test_view_calendar_access_denied_instructor(self, client, instructor_user):
        """Test that instructors cannot access the student calendar view."""
        self.login(client, 'instructor', 'password')

        # Test without following redirects to verify we get a redirect response
        response = client.get('/view', follow_redirects=False)

        # Should be redirected (status code 302)
        assert response.status_code == 302

        # Verify redirect location (should go to home page or another page)
        assert response.location == '/' or response.location.endswith('/home')

    def test_get_appointments(self, client, db, student_user, instructor_user, available_appointment):
        """Test getting available appointments."""
        self.login(client, 'student', 'password')

        # Current date plus/minus 1 month
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
        end_date = (datetime.now() + timedelta(days=30)).isoformat()

        response = client.get(
            f'/calendar/get_appointments?start={start_date}&end={end_date}&timeZone=UTC'
        )

        assert response.status_code == 200

        # Parse response and check appointment data
        appointments = json.loads(response.data)
        assert len(appointments) > 0

        # Verify appointment details
        appointment = appointments[0]
        assert appointment['id'] == available_appointment.id
        assert appointment['titleMessage'] == 'Dostępny'
        assert appointment['color'] == '#1B8359'  # Available appointment color

    def test_book_appointment_success(self, client, db, student_user, available_appointment):
        """Test successfully booking an appointment."""
        self.login(client, 'student', 'password')

        appointment_id = available_appointment.id
        booking_data = {
            'topic': 'Test consultation topic'
        }

        response = client.post(
            f'/calendar/book/{appointment_id}',
            data=json.dumps(booking_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify appointment was updated
        appointment = Appointment.query.get(appointment_id)
        assert appointment.is_available is False
        assert appointment.student_id == student_user.id
        assert appointment.topic == 'Test consultation topic'
        assert appointment.status == 'pending'

        # Verify notification was created
        notification = Notification.query.filter_by(
            user_id=appointment.instructor_id,
            related_id=appointment_id
        ).first()
        assert notification is not None
        assert notification.type == 'appointment'

    def test_book_appointment_unavailable(self, client, db, student_user, instructor_user):
        """Test booking an already reserved appointment."""
        self.login(client, 'student', 'password')

        # Create an already booked appointment
        start_time = datetime.now(pytz.UTC) + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        booked_appointment = Appointment(
            instructor_id=instructor_user.id,
            student_id=student_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=False,
            topic='Already booked'
        )
        db.session.add(booked_appointment)
        db.session.commit()

        booking_data = {
            'topic': 'Attempt to rebook'
        }

        response = client.post(
            f'/calendar/book/{booked_appointment.id}',
            data=json.dumps(booking_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert 'już zarezerwowany' in response_data['message']

    def test_book_appointment_too_soon(self, client, db, student_user, instructor_user):
        """Test booking an appointment less than 30 minutes from now."""
        self.login(client, 'student', 'password')

        # Create an appointment that's too soon
        start_time = datetime.now(pytz.UTC) + timedelta(minutes=15)
        end_time = start_time + timedelta(hours=1)

        soon_appointment = Appointment(
            instructor_id=instructor_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        db.session.add(soon_appointment)
        db.session.commit()

        booking_data = {
            'topic': 'Attempt to book soon'
        }

        response = client.post(
            f'/calendar/book/{soon_appointment.id}',
            data=json.dumps(booking_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert 'mniej niż 30 minut' in response_data['message']

    def test_cancel_appointment_success(self, client, db, student_user, instructor_user):
        """Test successfully canceling an appointment."""
        self.login(client, 'student', 'password')

        # Create a booked appointment
        start_time = datetime.now(pytz.UTC) + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        booked_appointment = Appointment(
            instructor_id=instructor_user.id,
            student_id=student_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=False,
            topic='To be canceled',
            status='pending'
        )
        db.session.add(booked_appointment)
        db.session.commit()

        response = client.post(f'/calendar/cancel/{booked_appointment.id}')

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify appointment was updated
        appointment = Appointment.query.get(booked_appointment.id)
        assert appointment.is_available is True
        assert appointment.student_id is None
        assert appointment.topic is None
        assert appointment.status == 'available'

        # Verify notification was created
        notification = Notification.query.filter_by(
            user_id=instructor_user.id,
            related_id=booked_appointment.id
        ).first()
        assert notification is not None
        assert notification.type == 'appointment'
        assert 'anulowana' in notification.message

    def test_cancel_appointment_not_owner(self, client, db, student_user, instructor_user):
        """Test canceling an appointment that doesn't belong to the user."""
        # Create another student
        other_student = User(
            username='otherstudent',
            email='other@example.com',
            first_name='Other',
            last_name='Student'
        )
        other_student.set_password('password')
        db.session.add(other_student)
        db.session.commit()

        # Create a booked appointment for the other student
        start_time = datetime.now(pytz.UTC) + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)

        other_appointment = Appointment(
            instructor_id=instructor_user.id,
            student_id=other_student.id,
            start_time=start_time,
            end_time=end_time,
            is_available=False,
            topic='Other student appointment',
            status='pending'
        )
        db.session.add(other_appointment)
        db.session.commit()

        # Login as the first student
        self.login(client, 'student', 'password')

        # Try to cancel other student's appointment
        response = client.post(f'/calendar/cancel/{other_appointment.id}')

        assert response.status_code == 403
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert 'własne terminy' in response_data['message']