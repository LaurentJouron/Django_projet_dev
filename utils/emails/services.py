import threading
from django.core.mail import EmailMessage


def send_email_async(subject, message, sender, recipients):
    def _send():
        email = EmailMessage(subject, message, sender, recipients)
        email.send()

    threading.Thread(target=_send).start()
