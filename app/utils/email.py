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

def send_password_reset_email(user):
    """Send password reset email to user"""
    from app import db  # Import db here to avoid circular imports
    
    token = user.generate_password_reset_token()
    
    db.session.commit()
    
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    
    subject = "Meutch - Reset Your Password"
    
    text_content = f"""
Hello {user.first_name},

You have requested to reset your password for your Meutch account.

To reset your password, please click the link below:

{reset_url}

This link will expire in 1 hour. If you didn't request a password reset, please ignore this email.

If you continue to have trouble accessing your account, please contact our support team.

Best regards,
The Meutch Team
    """.strip()
    
    return send_email(user.email, subject, text_content)


def send_message_notification_email(message):
    """Send email notification for new messages"""
    from app.models import User  # Import here to avoid circular imports
    
    # Get the recipient user
    recipient = User.query.get(message.recipient_id)
    sender = User.query.get(message.sender_id)
    
    if not recipient or not sender:
        current_app.logger.error(f"User not found for message notification: recipient={message.recipient_id}, sender={message.sender_id}")
        return False
    
    # Check if recipient has email notifications enabled
    if not recipient.email_notifications_enabled:
        current_app.logger.info(f"Email notifications disabled for user {recipient.id}, skipping notification")
        return True  # Return True since this is not an error
    
    # Generate the conversation URL
    conversation_url = url_for('main.view_conversation', message_id=message.id, _external=True)
    
    # Determine the subject and email content based on message type
    if message.is_loan_request_message:
        if message.loan_request.status == 'pending':
            subject = f"Meutch - New Loan Request for {message.item.name}"
            email_type = "loan request"
        elif message.loan_request.status == 'approved':
            subject = f"Meutch - Loan Request Approved for {message.item.name}"
            email_type = "loan approval"
        elif message.loan_request.status == 'denied':
            subject = f"Meutch - Loan Request Denied for {message.item.name}"
            email_type = "loan denial"
        elif message.loan_request.status == 'completed':
            subject = f"Meutch - Loan Completed for {message.item.name}"
            email_type = "loan completion"
        elif message.loan_request.status == 'canceled':
            subject = f"Meutch - Loan Request Canceled for {message.item.name}"
            email_type = "loan cancellation"
        else:
            # Strict validation: raise exception for unknown statuses
            raise ValueError(f"Unknown loan request status '{message.loan_request.status}' for message {message.id}. "
                           f"Valid statuses are: pending, approved, denied, completed, canceled")
    else:
        subject = f"Meutch - New Message about {message.item.name}"
        email_type = "message"
    
    text_content = f"""
Hello {recipient.first_name},

You have received a new {email_type} on Meutch from {sender.first_name} {sender.last_name}.

Item: {message.item.name}
From: {sender.first_name} {sender.last_name}

Message:
{message.body}

To view the full conversation and respond, click here:
{conversation_url}

You can also log into your Meutch account to view all your messages at any time.

Best regards,
The Meutch Team
    """.strip()
    
    # Create HTML content for better presentation
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">You have a new {email_type} on Meutch</h2>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>From:</strong> {sender.first_name} {sender.last_name}</p>
            <p><strong>Item:</strong> {message.item.name}</p>
        </div>
        
        <div style="background-color: white; padding: 20px; border-left: 4px solid #007bff; margin: 20px 0;">
            <h3>Message:</h3>
            <p style="white-space: pre-line;">{message.body}</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{conversation_url}" 
               style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Conversation & Respond
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            You can also log into your Meutch account to view all your messages at any time.
        </p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            Best regards,<br>
            The Meutch Team
        </p>
    </body>
    </html>
    """
    
    return send_email(recipient.email, subject, text_content, html_content)


def send_account_deletion_email(user_email, user_first_name):
    """Send account deletion confirmation email"""
    subject = "Meutch - Account Successfully Deleted"
    
    text_content = f"""
Hello {user_first_name},

This email confirms that your Meutch account has been successfully deleted as requested.

Your personal information and profile have been removed from our system. Your name will continue to appear in message history and loan records to preserve context for other users, but your account can no longer be used to log in.

Any active loans will continue normally until their end date. Your items without active loans have been permanently removed.

If you deleted your account by mistake or have any questions, please contact our support team as soon as possible.

Thank you for being part of the Meutch community. We're sorry to see you go!

Best regards,
The Meutch Team
    """.strip()
    
    return send_email(user_email, subject, text_content)