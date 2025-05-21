import unittest
from calendarproject.app import create_app
from calendarproject.extensions import db
from calendarproject.models.user import User

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_register_and_login(self):
        # Test user registration
        response = self.client.post('/auth/register', data={
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'testpass'
        })
        self.assertEqual(response.status_code, 302)

        # Test user login
        response = self.client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        self.assertEqual(response.status_code, 302)

if __name__ == '__main__':
    unittest.main()