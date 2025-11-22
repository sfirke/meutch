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
        
        # Check email allowlist (for staging/testing environments)
        allowlist = current_app.config.get('EMAIL_ALLOWLIST')
        if allowlist is not None:  # Allowlist is configured
            if to_email.lower() not in allowlist:
                current_app.logger.info(f"Email to {to_email} blocked by allowlist. Subject: {subject}")
                return True  # Return True since this is not an error - just filtered
        
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
    from app import db
    
    # Get the recipient user
    recipient = db.session.get(User, message.recipient_id)
    sender = db.session.get(User, message.sender_id)
    
    if not recipient or not sender:
        current_app.logger.error(f"User not found for message notification: recipient={message.recipient_id}, sender={message.sender_id}")
        return False
    
    # Generate the conversation URL
    conversation_url = url_for('main.view_conversation', message_id=message.id, _external=True)
    
    # Determine the subject and email content based on message type
    if message.is_loan_request_message:
        # Check if this is a loan extension message (owner extending the due date)
        if message.loan_request.status == 'approved' and 'has been extended' in message.body:
            subject = f"Meutch - Loan Extended for {message.item.name}"
            email_type = "loan extension"
        elif message.loan_request.status == 'pending':
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


def send_circle_join_request_notification_email(join_request):
    """Send email notification to circle admins when a user requests to join"""
    from app.models import User, circle_members  # Import here to avoid circular imports
    from sqlalchemy import and_
    
    # Get the circle and requesting user
    circle = join_request.circle
    requesting_user = join_request.user
    
    if not circle or not requesting_user:
        current_app.logger.error(f"Circle or user not found for join request notification: circle={join_request.circle_id}, user={join_request.user_id}")
        return False
    
    # Get all admins of the circle
    admin_users = User.query.join(
        circle_members,
        and_(
            User.id == circle_members.c.user_id,
            circle_members.c.circle_id == circle.id,
            circle_members.c.is_admin == True
        )
    ).all()
    
    if not admin_users:
        current_app.logger.error(f"No admins found for circle {circle.id}")
        return False
    
    # Generate the circle details URL
    circle_url = url_for('circles.view_circle', circle_id=circle.id, _external=True)
    
    subject = f"Meutch - New Join Request for {circle.name}"
    
    success_count = 0
    for admin in admin_users:
        # Link to the requesting user's profile for quick review context
        profile_url = url_for('main.user_profile', user_id=requesting_user.id, _external=True)

        text_content = f"""
Hello {admin.first_name},

You have received a new request to join your circle "{circle.name}" on Meutch.

Requesting User: {requesting_user.first_name} {requesting_user.last_name}
Profile: {profile_url}
Circle: {circle.name}
""" + (f"""
Request Message:
{join_request.message}
""" if join_request.message else "") + f"""
To review this request and take action, visit your circle:
{circle_url}

You can approve or reject the request from your circle's management page.

Best regards,
The Meutch Team
        """.strip()
        
        # Create HTML content for better presentation
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #333;">New Join Request for Your Circle</h2>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Requesting User:</strong> <a href="{profile_url}" style="color: #007bff; text-decoration: none;">{requesting_user.first_name} {requesting_user.last_name}</a></p>
                <p><strong>Circle:</strong> {circle.name}</p>
            </div>
            """ + (f"""
            <div style="background-color: white; padding: 20px; border-left: 4px solid #007bff; margin: 20px 0;">
                <h3>Request Message:</h3>
                <p style="white-space: pre-line;">{join_request.message}</p>
            </div>
            """ if join_request.message else "") + f"""
            <div style="text-align: center; margin: 30px 0;">
                <a href="{circle_url}" 
                   style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Review Join Request
                </a>
            </div>
            
            <p style="color: #666; font-size: 14px;">
                You can approve or reject the request from your circle's management page.
            </p>
            
            <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
            <p style="color: #999; font-size: 12px;">
                Best regards,<br>
                The Meutch Team
            </p>
        </body>
        </html>
        """
        
        if send_email(admin.email, subject, text_content, html_content):
            success_count += 1
        else:
            current_app.logger.error(f"Failed to send circle join request notification to admin {admin.id}")
    
    return success_count > 0


def send_circle_join_request_decision_email(join_request):
    """Send email notification to user when their join request is acted upon"""
    from app.models import User  # Import here to avoid circular imports
    
    # Get the circle and requesting user
    circle = join_request.circle
    requesting_user = join_request.user
    
    if not circle or not requesting_user:
        current_app.logger.error(f"Circle or user not found for join request decision notification: circle={join_request.circle_id}, user={join_request.user_id}")
        return False
    
    # Generate the circle details URL
    circle_url = url_for('circles.view_circle', circle_id=circle.id, _external=True)
    
    # Determine the subject and email content based on status
    if join_request.status == 'approved':
        subject = f"Meutch - Join Request Approved for {circle.name}"
        decision_text = "approved"
        button_text = "View Circle"
        html_color = "#28a745"
    elif join_request.status == 'rejected':
        subject = f"Meutch - Join Request Denied for {circle.name}"
        decision_text = "denied"
        button_text = "Browse Other Circles"
        html_color = "#dc3545"
    else:
        current_app.logger.error(f"Unknown join request status '{join_request.status}' for request {join_request.id}")
        return False
    
    text_content = f"""
Hello {requesting_user.first_name},

Your request to join the circle "{circle.name}" has been {decision_text}.

Circle: {circle.name}
Status: {decision_text.title()}
""" + (f"""
To view the circle, visit:
{circle_url}
""" if join_request.status == 'approved' else f"""
You can search for other circles to join by visiting your Meutch account.
""") + f"""
Thank you for using Meutch!

Best regards,
The Meutch Team
    """.strip()
    
    # Create HTML content for better presentation
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">Circle Join Request {decision_text.title()}</h2>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Circle:</strong> {circle.name}</p>
            <p><strong>Status:</strong> <span style="color: {html_color}; font-weight: bold;">{decision_text.title()}</span></p>
        </div>
        """ + (f"""
        <div style="text-align: center; margin: 30px 0;">
            <a href="{circle_url}" 
               style="background-color: {html_color}; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                {button_text}
            </a>
        </div>
        """ if join_request.status == 'approved' else f"""
        <p style="color: #666; font-size: 14px;">
            You can search for other circles to join by visiting your Meutch account.
        </p>
        """) + f"""
        <p style="color: #666; font-size: 14px;">
            Thank you for using Meutch!
        </p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            Best regards,<br>
            The Meutch Team
        </p>
    </body>
    </html>
    """
    
    return send_email(requesting_user.email, subject, text_content, html_content)


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


def send_loan_due_soon_email(loan):
    """Send 3-day reminder email to borrower that loan is due soon"""
    from app.models import User  # Import here to avoid circular imports
    from app import db
    
    borrower = db.session.get(User, loan.borrower_id)
    owner = db.session.get(User, loan.item.owner_id)
    
    if not borrower or not owner:
        current_app.logger.error(f"User not found for loan due soon email: borrower={loan.borrower_id}, owner={loan.item.owner_id}")
        return False
    
    # Generate the item URL
    item_url = url_for('main.item_detail', item_id=loan.item_id, _external=True)
    
    subject = f"Meutch - Reminder: {loan.item.name} is due in 3 days"
    
    text_content = f"""
Hello {borrower.first_name},

This is a friendly reminder that the item you borrowed is due back soon.

Item: {loan.item.name}
Owner: {owner.first_name} {owner.last_name}
Due Date: {loan.end_date.strftime('%B %d, %Y')} (in 3 days)

Please make arrangements to return the item by the due date. If you need more time, please contact the owner to discuss extending the loan.

You can view the item details here:
{item_url}

Thank you for being a responsible borrower!

Best regards,
The Meutch Team
    """.strip()
    
    # Create HTML content
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">Loan Due Soon Reminder</h2>
        
        <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107; margin: 20px 0;">
            <p style="margin: 0;"><strong>⏰ Your borrowed item is due back in 3 days</strong></p>
        </div>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Item:</strong> {loan.item.name}</p>
            <p><strong>Owner:</strong> {owner.first_name} {owner.last_name}</p>
            <p><strong>Due Date:</strong> {loan.end_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Please make arrangements to return the item by the due date. If you need more time, please contact the owner to discuss extending the loan.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{item_url}" 
               style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Item Details
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Thank you for being a responsible borrower!
        </p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            Best regards,<br>
            The Meutch Team
        </p>
    </body>
    </html>
    """
    
    return send_email(borrower.email, subject, text_content, html_content)


def send_loan_due_today_borrower_email(loan):
    """Send due date reminder email to borrower"""
    from app.models import User  # Import here to avoid circular imports
    from app import db
    
    borrower = db.session.get(User, loan.borrower_id)
    owner = db.session.get(User, loan.item.owner_id)
    
    if not borrower or not owner:
        current_app.logger.error(f"User not found for loan due today email: borrower={loan.borrower_id}, owner={loan.item.owner_id}")
        return False
    
    # Generate the item URL
    item_url = url_for('main.item_detail', item_id=loan.item_id, _external=True)
    
    subject = f"Meutch - {loan.item.name} is due back today"
    
    text_content = f"""
Hello {borrower.first_name},

This is a reminder that the item you borrowed is due back today.

Item: {loan.item.name}
Owner: {owner.first_name} {owner.last_name}
Due Date: Today, {loan.end_date.strftime('%B %d, %Y')}

Please return the item to the owner as soon as possible. If you need more time or have already returned it, please contact the owner to coordinate.

You can view the item details here:
{item_url}

Thank you for your prompt attention!

Best regards,
The Meutch Team
    """.strip()
    
    # Create HTML content
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">Item Due Today</h2>
        
        <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107; margin: 20px 0;">
            <p style="margin: 0;"><strong>📅 Your borrowed item is due back today</strong></p>
        </div>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Item:</strong> {loan.item.name}</p>
            <p><strong>Owner:</strong> {owner.first_name} {owner.last_name}</p>
            <p><strong>Due Date:</strong> Today, {loan.end_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Please return the item to the owner as soon as possible. If you need more time or have already returned it, please contact the owner to coordinate.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{item_url}" 
               style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Item Details
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Thank you for your prompt attention!
        </p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            Best regards,<br>
            The Meutch Team
        </p>
    </body>
    </html>
    """
    
    return send_email(borrower.email, subject, text_content, html_content)


def send_loan_due_today_owner_email(loan):
    """Send due date notification email to owner"""
    from app.models import User  # Import here to avoid circular imports
    from app import db
    
    borrower = db.session.get(User, loan.borrower_id)
    owner = db.session.get(User, loan.item.owner_id)
    
    if not borrower or not owner:
        current_app.logger.error(f"User not found for loan due today owner email: borrower={loan.borrower_id}, owner={loan.item.owner_id}")
        return False
    
    # Generate the item URL
    item_url = url_for('main.item_detail', item_id=loan.item_id, _external=True)
    # Generate the extend loan URL for owners to extend the loan
    extend_url = url_for('main.extend_loan', loan_id=loan.id, _external=True)
    
    subject = f"Meutch - Your item {loan.item.name} is due back today"
    
    text_content = f"""
Hello {owner.first_name},

This is a notification that your item is due to be returned today.

Item: {loan.item.name}
Borrower: {borrower.first_name} {borrower.last_name}
Due Date: Today, {loan.end_date.strftime('%B %d, %Y')}

If you need to coordinate the return, please reach out to them. Or you can extend the loan to give them more time:
{extend_url}

You can view the item details here:
{item_url}

Thank you for sharing with your community!

Best regards,
The Meutch Team
    """.strip()
    
    # Create HTML content
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">Item Due Back Today</h2>
        
        <div style="background-color: #d1ecf1; padding: 20px; border-radius: 8px; border-left: 4px solid #17a2b8; margin: 20px 0;">
            <p style="margin: 0;"><strong>📅 Your loaned item is due back today</strong></p>
        </div>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Item:</strong> {loan.item.name}</p>
            <p><strong>Borrower:</strong> {borrower.first_name} {borrower.last_name}</p>
            <p><strong>Due Date:</strong> Today, {loan.end_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            If you need to coordinate the return, please reach out to them. Or you can extend the loan to give them more time.
        </p>

        <div style="text-align: center; margin: 20px 0; display:flex; gap:12px; justify-content:center;">
            <a href="{item_url}" 
               style="background-color: #007bff; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Item Details
            </a>
            <a href="{extend_url}" 
               style="background-color: #28a745; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Extend Loan
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Thank you for sharing with your community!
        </p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            Best regards,<br>
            The Meutch Team
        </p>
    </body>
    </html>
    """
    
    return send_email(owner.email, subject, text_content, html_content)


def send_loan_overdue_borrower_email(loan, days_overdue):
    """Send overdue reminder email to borrower"""
    from app.models import User  # Import here to avoid circular imports
    from app import db
    
    borrower = db.session.get(User, loan.borrower_id)
    owner = db.session.get(User, loan.item.owner_id)
    
    if not borrower or not owner:
        current_app.logger.error(f"User not found for loan overdue email: borrower={loan.borrower_id}, owner={loan.item.owner_id}")
        return False
    
    # Generate the item URL
    item_url = url_for('main.item_detail', item_id=loan.item_id, _external=True)
    
    subject = f"Meutch - Reminder: {loan.item.name} is {days_overdue} day{'s' if days_overdue != 1 else ''} overdue"
    
    text_content = f"""
Hello {borrower.first_name},

This is a reminder that the item you borrowed is now overdue.

Item: {loan.item.name}
Owner: {owner.first_name} {owner.last_name}
Due Date: {loan.end_date.strftime('%B %d, %Y')}
Days Overdue: {days_overdue}

Please return the item to the owner as soon as possible. If you need more time, please contact the owner immediately to request an extension or discuss the situation.

You can view the item details here:
{item_url}

Thank you for your prompt attention to this matter.

Best regards,
The Meutch Team
    """.strip()
    
    # Create HTML content
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">Overdue Item Reminder</h2>
        
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; border-left: 4px solid #dc3545; margin: 20px 0;">
            <p style="margin: 0;"><strong>⚠️ Your borrowed item is {days_overdue} day{'s' if days_overdue != 1 else ''} overdue</strong></p>
        </div>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Item:</strong> {loan.item.name}</p>
            <p><strong>Owner:</strong> {owner.first_name} {owner.last_name}</p>
            <p><strong>Due Date:</strong> {loan.end_date.strftime('%B %d, %Y')}</p>
            <p><strong>Days Overdue:</strong> <span style="color: #dc3545; font-weight: bold;">{days_overdue}</span></p>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Please return the item to the owner as soon as possible. If you need more time, please contact the owner immediately to request an extension or discuss the situation.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{item_url}" 
               style="background-color: #dc3545; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Item Details
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Thank you for your prompt attention to this matter.
        </p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            Best regards,<br>
            The Meutch Team
        </p>
    </body>
    </html>
    """
    
    return send_email(borrower.email, subject, text_content, html_content)


def send_loan_overdue_owner_email(loan, days_overdue):
    """Send overdue notification email to owner"""
    from app.models import User  # Import here to avoid circular imports
    from app import db
    
    borrower = db.session.get(User, loan.borrower_id)
    owner = db.session.get(User, loan.item.owner_id)
    
    if not borrower or not owner:
        current_app.logger.error(f"User not found for loan overdue owner email: borrower={loan.borrower_id}, owner={loan.item.owner_id}")
        return False
    
    # Generate the item URL
    item_url = url_for('main.item_detail', item_id=loan.item_id, _external=True)
    # Generate the extend loan URL for owners to extend the loan
    extend_url = url_for('main.extend_loan', loan_id=loan.id, _external=True)
    
    subject = f"Meutch - Your item {loan.item.name} is {days_overdue} day{'s' if days_overdue != 1 else ''} overdue"
    
    text_content = f"""
Hello {owner.first_name},

This is a notification that your loaned item is now overdue.

Item: {loan.item.name}
Borrower: {borrower.first_name} {borrower.last_name}
Due Date: {loan.end_date.strftime('%B %d, %Y')}
Days Overdue: {days_overdue}

If you need to coordinate the return, please reach out to them. Or you can extend the loan to give them more time:
{extend_url}

You can view the item details here:
{item_url}

Thank you for your patience.

Best regards,
The Meutch Team
    """.strip()
    
    # Create HTML content
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #333;">Loaned Item Overdue</h2>
        
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; border-left: 4px solid #dc3545; margin: 20px 0;">
            <p style="margin: 0;"><strong>⚠️ Your loaned item is {days_overdue} day{'s' if days_overdue != 1 else ''} overdue</strong></p>
        </div>
        
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Item:</strong> {loan.item.name}</p>
            <p><strong>Borrower:</strong> {borrower.first_name} {borrower.last_name}</p>
            <p><strong>Due Date:</strong> {loan.end_date.strftime('%B %d, %Y')}</p>
            <p><strong>Days Overdue:</strong> <span style="color: #dc3545; font-weight: bold;">{days_overdue}</span></p>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            If you need to coordinate the return, please reach out to them. Or you can extend the loan to give them more time.
        </p>
        
        <div style="text-align: center; margin: 20px 0; display:flex; gap:12px; justify-content:center;">
            <a href="{item_url}" 
               style="background-color: #007bff; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Item Details
            </a>
            <a href="{extend_url}" 
               style="background-color: #28a745; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Extend Loan
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Thank you for your patience.
        </p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            Best regards,<br>
            The Meutch Team
        </p>
    </body>
    </html>
    """
    
    return send_email(owner.email, subject, text_content, html_content)