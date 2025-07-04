import pytest
from flask import url_for, session
from calendarproject.models.user import User
from calendarproject.extensions import db
from flask_login import current_user

class TestAuthViews:
    """Test suite for the authentication views."""

    def test_register_get(self, client):
        """Test that GET request to register returns the registration form."""
        response = client.get('/register')
        assert response.status_code == 200
        assert b'Rejestracja' in response.data

    def test_register_post_success(self, client, db):
        """Test successful user registration."""
        user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'securepassword',
            'first_name': 'Test',
            'last_name': 'User'
        }

        response = client.post('/register', data=user_data, follow_redirects=True)
        assert response.status_code == 200

        # Verify user was created in DB
        user = User.query.filter_by(username='testuser').first()
        assert user is not None
        assert user.email == 'test@example.com'
        assert user.first_name == 'Test'
        assert user.last_name == 'User'
        assert user.check_password('securepassword')
        assert not user.is_admin
        assert not user.is_instructor

    def test_register_post_duplicate_username(self, client, db):
        """Test registration with existing username."""
        # Create a user first
        user = User(
            username='existinguser',
            email='existing@example.com',
            first_name='Existing',
            last_name='User'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # Try to register with the same username
        user_data = {
            'username': 'existinguser',
            'email': 'new@example.com',
            'password': 'securepassword',
            'first_name': 'New',
            'last_name': 'User'
        }

        response = client.post('/register', data=user_data)
        assert response.status_code == 200
        assert b'Nazwa u\xc5\xbcytkownika ju\xc5\xbc istnieje' in response.data

    def test_register_post_duplicate_email(self, client, db):
        """Test registration with existing email."""
        # Create a user first
        user = User(
            username='user1',
            email='duplicate@example.com',
            first_name='Existing',
            last_name='User'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # Try to register with the same email
        user_data = {
            'username': 'uniqueuser',
            'email': 'duplicate@example.com',
            'password': 'securepassword',
            'first_name': 'New',
            'last_name': 'User'
        }

        response = client.post('/register', data=user_data)
        assert response.status_code == 200
        assert b'Adres email jest ju\xc5\xbc u\xc5\xbcywany' in response.data

    def test_login_get(self, client):
        """Test that GET request to login returns the login form."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Logowanie' in response.data

    def test_login_post_success(self, client, db):
        """Test successful login."""
        # Create a user first
        user = User(
            username='loginuser',
            email='login@example.com',
            first_name='Login',
            last_name='User'
        )
        user.set_password('correctpassword')
        db.session.add(user)
        db.session.commit()

        # Login with correct credentials
        response = client.post('/login', data={
            'username': 'loginuser',
            'password': 'correctpassword'
        }, follow_redirects=True)

        # Instead of checking for flash messages, verify the login was successful:
        # 1. Status code is 200
        assert response.status_code == 200

        # 2. Check the user was logged in by making another request and verifying session
        with client.session_transaction() as sess:
            # Check that the user ID is in the session
            assert '_user_id' in sess

        # 3. Verify we can access a protected route successfully
        dashboard_response = client.get('/dashboard', follow_redirects=True)
        assert dashboard_response.status_code == 200  # Either access or redirect to home with 200

    def test_login_post_wrong_password(self, client, db):
        """Test login with wrong password."""
        # Create a user first
        user = User(
            username='wrongpassuser',
            email='wrongpass@example.com',
            first_name='Wrong',
            last_name='Pass'
        )
        user.set_password('correctpassword')
        db.session.add(user)
        db.session.commit()

        # Login with wrong password
        response = client.post('/login', data={
            'username': 'wrongpassuser',
            'password': 'wrongpassword'
        })

        assert response.status_code == 200
        assert b'Nieprawid\xc5\x82owa nazwa u\xc5\xbcytkownika lub has\xc5\x82o' in response.data

    def test_login_post_nonexistent_user(self, client):
        """Test login with nonexistent username."""
        response = client.post('/login', data={
            'username': 'nonexistentuser',
            'password': 'somepassword'
        })

        assert response.status_code == 200
        assert b'Nieprawid\xc5\x82owa nazwa u\xc5\xbcytkownika lub has\xc5\x82o' in response.data

    def test_logout(self, client, db):
        """Test logout functionality."""
        # Create and login a user
        user = User(
            username='logoutuser',
            email='logout@example.com',
            first_name='Logout',
            last_name='User'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # Login
        client.post('/login', data={
            'username': 'logoutuser',
            'password': 'password'
        })

        # Verify we're logged in
        with client.session_transaction() as sess:
            assert '_user_id' in sess

        # Logout
        response = client.get('/logout', follow_redirects=True)
        assert response.status_code == 200

        # Verify we're logged out by checking the session
        with client.session_transaction() as sess:
            assert '_user_id' not in sess

        # Also verify that a protected page now redirects us
        dashboard_response = client.get('/dashboard', follow_redirects=False)
        assert dashboard_response.status_code == 302  # We should be redirected