import requests
import os
from flask import current_app, url_for


def send_email(to_email, subject, text_content, html_content=None):
    """Send email using Mailgun API"""
    try:
        api_key = current_app.config.get('MAILGUN_API_KEY')
        domain = current_app.config.get('MAILGUN_DOMAIN')
        
        if not api_key or not domain:
            current_app.logger.error("Mailgun configuration missing")
            return False
            
        from_email = f"Meutch <postmaster@{domain}>"
        
        data = {
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "text": text_content
        }
        
        if html_content:
            data["html"] = html_content
            
        response = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data=data
        )
        
        if response.status_code == 200:
            current_app.logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            current_app.logger.error(f"Failed to send email: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        return False


def send_confirmation_email(user):
    """Send email confirmation to user"""
    from app import db  # Import db here to avoid circular imports
    
    token = user.generate_confirmation_token()
    
    db.session.commit()
    
    confirmation_url = url_for('auth.confirm_email', token=token, _external=True)
    
    print(f"Confirmation URL: {confirmation_url}")
    
    subject = "Welcome to Meutch - Please confirm your email"
    
    text_content = f"""
Hello {user.first_name},

Welcome to Meutch!

To complete your registration, please click the link below to confirm your email address:

{confirmation_url}

This link will expire in 24 hours. If you didn't create an account with Meutch, please ignore this email.

Best regards,
The Meutch Team
    """.strip()
    
    return send_email(user.email, subject, text_content)