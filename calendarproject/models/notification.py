from calendarproject.extensions import db
from datetime import datetime

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(50), nullable=False)  # New field for notification type
    related_id = db.Column(db.Integer)  # New field to store related item's ID (e.g., appointment_id)

    def __repr__(self):
        return f'<Notification {self.id}>'