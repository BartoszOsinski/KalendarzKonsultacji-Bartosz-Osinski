from calendarproject.extensions import db
from datetime import datetime

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    topic = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='pending')

    instructor = db.relationship('User', foreign_keys=[instructor_id], backref='instructor_appointments')
    student = db.relationship('User', foreign_keys=[student_id], backref='student_appointments')

    def __repr__(self):
        return f'<Appointment {self.id}>'