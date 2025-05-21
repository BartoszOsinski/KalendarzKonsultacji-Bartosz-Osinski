from flask_mail import Message
from calendarproject.extensions import mail

def send_email_notification(to, subject, body):
    msg = Message(subject, recipients=[to])
    msg.body = body
    mail.send(msg)

def notify_instructor_new_appointment(instructor, appointment):
    subject = "New Appointment Request"
    body = f"A new appointment has been requested for {appointment.start_time}."
    # send_email_notification(instructor.email, subject, body)

def notify_student_appointment_status(student, appointment):
    subject = f"Appointment {appointment.status.capitalize()}"
    body = f"Your appointment for {appointment.start_time} has been {appointment.status}."
    # send_email_notification(student.email, subject, body)