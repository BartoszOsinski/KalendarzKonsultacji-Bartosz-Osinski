import pytest
import json
from datetime import datetime
import pytz
from flask import url_for
from flask_login import login_user
from calendarproject.models.user import User
from calendarproject.models.appointment import Appointment
from calendarproject.models.notification import Notification
from calendarproject.extensions import db

class TestAdminViews:
    """Test suite for the admin dashboard and functionality."""

    @pytest.fixture
    def admin_user(self, db):
        """Create an admin user for testing."""
        admin = User(
            username='adminuser',
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            is_admin=True
        )
        admin.set_password('adminpassword')
        db.session.add(admin)
        db.session.commit()
        return admin

    @pytest.fixture
    def regular_user(self, db):
        """Create a regular user for testing."""
        user = User(
            username='regularuser',
            email='regular@example.com',
            first_name='Regular',
            last_name='User',
            is_admin=False
        )
        user.set_password('userpassword')
        db.session.add(user)
        db.session.commit()
        return user

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

    def login(self, client, username, password):
        """Helper function to login a user."""
        return client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_dashboard_access_admin(self, client, admin_user):
        """Test that admin can access dashboard."""
        self.login(client, 'adminuser', 'adminpassword')
        response = client.get('/dashboard')
        assert response.status_code == 200

    def test_dashboard_access_denied_regular_user(self, client, regular_user):
        """Test that regular users cannot access admin dashboard."""
        self.login(client, 'regularuser', 'userpassword')

        # Instead of checking for flash messages that may vary, verify we get redirected
        # away from the admin dashboard to the home page
        response = client.get('/dashboard', follow_redirects=False)
        assert response.status_code == 302  # 302 is a redirection status code

        # Check that we're being redirected to the home page
        assert response.location == '/' or response.location.endswith('/home')

    def test_create_instructor_success(self, client, admin_user):
        """Test successful instructor creation by admin."""
        self.login(client, 'adminuser', 'adminpassword')

        # Create new instructor
        instructor_data = {
            'username': 'newinstructor',
            'email': 'newinstructor@example.com',
            'password': 'instructorpass',
            'first_name': 'New',
            'last_name': 'Instructor'
        }

        response = client.post('/create_instructor',
                               data=instructor_data,
                               follow_redirects=True)

        assert response.status_code == 200

        # Check if the success message has been shown
        assert b'utworzony' in response.data.lower()

        # Verify instructor was created
        instructor = User.query.filter_by(username='newinstructor').first()
        assert instructor is not None
        assert instructor.is_instructor is True
        assert instructor.first_name == 'New'
        assert instructor.last_name == 'Instructor'
        assert instructor.email == 'newinstructor@example.com'

    def test_create_instructor_duplicate_username(self, client, admin_user, instructor_user):
        """Test instructor creation with duplicate username."""
        self.login(client, 'adminuser', 'adminpassword')

        # Try creating instructor with existing username
        instructor_data = {
            'username': 'instructor',  # Already exists
            'email': 'different@example.com',
            'password': 'instructorpass',
            'first_name': 'New',
            'last_name': 'Instructor'
        }

        response = client.post('/create_instructor',
                               data=instructor_data,
                               follow_redirects=True)

        assert response.status_code == 200
        assert b'ju\xc5\xbc istnieje' in response.data.lower()

    def test_create_instructor_access_denied(self, client, regular_user):
        """Test that regular users cannot create instructors."""
        self.login(client, 'regularuser', 'userpassword')

        instructor_data = {
            'username': 'attempted',
            'email': 'attempted@example.com',
            'password': 'password',
            'first_name': 'Attempted',
            'last_name': 'Instructor'
        }

        # Similar to dashboard access test, verify we get redirected rather than
        # looking for specific flash messages
        response = client.post('/create_instructor',
                               data=instructor_data,
                               follow_redirects=False)

        assert response.status_code == 302  # 302 is a redirection status code

        # Verify instructor was not created
        instructor = User.query.filter_by(username='attempted').first()
        assert instructor is None

    def test_delete_instructor_success(self, client, db, admin_user, instructor_user):
        """Test successful instructor deletion by admin."""
        self.login(client, 'adminuser', 'adminpassword')

        # Create appointment for instructor with proper datetime objects
        start_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=pytz.UTC)
        end_time = datetime(2025, 1, 1, 11, 0, 0, tzinfo=pytz.UTC)

        appointment = Appointment(
            instructor_id=instructor_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        db.session.add(appointment)
        db.session.commit()

        # Get instructor ID
        instructor_id = instructor_user.id

        # Delete instructor
        response = client.post(f'/admin/delete_instructor/{instructor_id}')

        # Check the response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'

        # Verify instructor was soft deleted
        instructor = User.query.get(instructor_id)
        assert instructor.deleted is True

        # Verify appointments were deleted
        appointments = Appointment.query.filter_by(instructor_id=instructor_id).all()
        assert len(appointments) == 0

    def test_delete_instructor_not_admin(self, client, db, regular_user, instructor_user):
        """Test that non-admin users cannot delete instructors."""
        # Ensure DB is clean after previous test failures
        db.session.rollback()

        self.login(client, 'regularuser', 'userpassword')

        instructor_id = instructor_user.id

        # Attempt to delete instructor
        response = client.post(f'/admin/delete_instructor/{instructor_id}')

        assert response.status_code == 403
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert 'Odmowa dostępu' in response_data['message']

        # Verify instructor was not deleted
        instructor = User.query.get(instructor_id)
        assert instructor.deleted is False

    def test_delete_instructor_notifications(self, client, db, admin_user, instructor_user):
        """Test that notifications are created when an instructor with booked appointments is deleted."""
        # Ensure DB is clean after previous test failures
        db.session.rollback()

        # Create a student user
        student = User(
            username='student',
            email='student@example.com',
            first_name='Student',
            last_name='User'
        )
        student.set_password('password')
        db.session.add(student)
        db.session.commit()

        # Create a booked appointment with proper datetime objects
        start_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=pytz.UTC)
        end_time = datetime(2025, 1, 1, 11, 0, 0, tzinfo=pytz.UTC)

        appointment = Appointment(
            instructor_id=instructor_user.id,
            student_id=student.id,
            start_time=start_time,
            end_time=end_time,
            is_available=False,
            topic='Test appointment'
        )
        db.session.add(appointment)
        db.session.commit()

        # Login as admin
        self.login(client, 'adminuser', 'adminpassword')

        # Delete instructor
        instructor_id = instructor_user.id
        response = client.post(f'/admin/delete_instructor/{instructor_id}')

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'
        assert response_data['notified_students'] == 1

        # Verify notification was created
        notification = Notification.query.filter_by(user_id=student.id).first()
        assert notification is not None
        assert notification.type == 'instructor_deleted'
        assert 'zostało usunięte' in notification.message or 'zostalo usuniete' in notification.message.lower()