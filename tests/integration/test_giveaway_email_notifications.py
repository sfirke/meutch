"""Integration tests for giveaway email notifications.

Tests verify:
1. Email sent on recipient selection (initial)
2. Email sent on reassignment (change recipient)
3. Email sent on interest expression
4. Previous recipient notified on release-to-all
5. Email failure doesn't block operation
"""
from unittest.mock import patch
from app import db
from app.models import GiveawayInterest, Message
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory
from conftest import login_user


class TestGiveawaySelectionEmail:
    """Test email notifications when selecting a recipient."""
    
    def test_email_sent_on_initial_recipient_selection(self, client, app, auth_user):
        """Test that email is sent when owner initially selects a recipient."""
        with app.app_context():
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.return_value = True
                
                response = client.post(f'/item/{giveaway.id}/select-recipient', data={
                    'selection_method': 'first'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify email was called
                assert mock_email.called
                call_args = mock_email.call_args[0]
                message = call_args[0]
                assert message.recipient_id == requester.id
                assert "selected" in message.body.lower() or "good news" in message.body.lower()
    
    def test_email_sent_on_random_selection(self, client, app, auth_user):
        """Test that email is sent when owner selects via random."""
        with app.app_context():
            owner = auth_user()
            requester1 = UserFactory()
            requester2 = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            for user in [requester1, requester2]:
                interest = GiveawayInterest(
                    item_id=giveaway.id,
                    user_id=user.id,
                    status='active'
                )
                db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                with patch('random.choice', return_value=GiveawayInterest.query.filter_by(
                    item_id=giveaway.id, user_id=requester1.id
                ).first()):
                    mock_email.return_value = True
                    
                    response = client.post(f'/item/{giveaway.id}/select-recipient', data={
                        'selection_method': 'random'
                    }, follow_redirects=True)
                    
                    assert response.status_code == 200
                    assert mock_email.called
    
    def test_email_failure_does_not_block_selection(self, client, app, auth_user):
        """Test that email failure doesn't prevent recipient selection."""
        with app.app_context():
            owner = auth_user()
            requester = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed'
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=requester.id,
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.side_effect = Exception("Email service unavailable")
                
                response = client.post(f'/item/{giveaway.id}/select-recipient', data={
                    'selection_method': 'first'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify selection still happened despite email failure
                db.session.refresh(giveaway)
                assert giveaway.claim_status == 'pending_pickup'
                assert giveaway.claimed_by_id == requester.id


class TestGiveawayReassignmentEmail:
    """Test email notifications when changing recipient."""
    
    def test_email_sent_to_new_recipient_on_reassignment(self, client, app, auth_user):
        """Test that email is sent to newly selected recipient on reassignment."""
        with app.app_context():
            owner = auth_user()
            previous_recipient = UserFactory()
            new_recipient = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=previous_recipient
            )
            
            # Previous recipient's interest - selected
            prev_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=previous_recipient.id,
                status='selected'
            )
            db.session.add(prev_interest)
            
            # New recipient's interest - still active
            new_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=new_recipient.id,
                status='active'
            )
            db.session.add(new_interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.return_value = True
                
                response = client.post(f'/item/{giveaway.id}/change-recipient', data={
                    'selection_method': 'next'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify email was called (should be called for new recipient)
                assert mock_email.called
                # Should be called at least once for the new recipient
                recipient_ids = [call[0][0].recipient_id for call in mock_email.call_args_list]
                assert new_recipient.id in recipient_ids
    
    def test_previous_recipient_notified_on_reassignment(self, client, app, auth_user):
        """Test that previous recipient receives both a message and email when de-selected.
        
        When a giveaway is reassigned to someone else, the previous recipient should
        receive both an in-app message AND an email notification to ensure they're
        promptly informed of the change.
        """
        with app.app_context():
            owner = auth_user()
            previous_recipient = UserFactory()
            new_recipient = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=previous_recipient
            )
            
            prev_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=previous_recipient.id,
                status='selected'
            )
            db.session.add(prev_interest)
            
            new_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=new_recipient.id,
                status='active'
            )
            db.session.add(new_interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.return_value = True
                
                response = client.post(f'/item/{giveaway.id}/change-recipient', data={
                    'selection_method': 'next'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify message was created for previous recipient
                prev_message = Message.query.filter_by(
                    recipient_id=previous_recipient.id,
                    item_id=giveaway.id
                ).first()
                assert prev_message is not None
                assert "different recipient" in prev_message.body.lower() or "selected" in prev_message.body.lower()
                
                # Verify email was sent to BOTH previous and new recipients
                # Previous recipient gets notified of de-selection, new recipient gets selection notice
                email_recipients = [call[0][0].recipient_id for call in mock_email.call_args_list]
                assert previous_recipient.id in email_recipients
                assert new_recipient.id in email_recipients
    
    def test_email_failure_does_not_block_reassignment(self, client, app, auth_user):
        """Test that email failure doesn't prevent reassignment."""
        with app.app_context():
            owner = auth_user()
            previous_recipient = UserFactory()
            new_recipient = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=previous_recipient
            )
            
            prev_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=previous_recipient.id,
                status='selected'
            )
            db.session.add(prev_interest)
            
            new_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=new_recipient.id,
                status='active'
            )
            db.session.add(new_interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.side_effect = Exception("Email service unavailable")
                
                response = client.post(f'/item/{giveaway.id}/change-recipient', data={
                    'selection_method': 'next'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify reassignment still happened
                db.session.refresh(giveaway)
                assert giveaway.claimed_by_id == new_recipient.id


class TestGiveawayInterestEmail:
    """Test that owner gets both in-app message and email on interest expression."""
    
    def test_owner_notified_on_public_giveaway_express_interest(self, client, app, auth_user):
        """Test that public giveaway owner receives in-app message and email when interest is expressed."""
        with app.app_context():
            owner = UserFactory()
            requester = auth_user()
            circle = CircleFactory()
            circle.members.append(owner)
            circle.members.append(requester)
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed'
            )
            db.session.commit()
            
            login_user(client, requester.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.return_value = True
                
                response = client.post(f'/item/{giveaway.id}/express-interest', data={
                    'message': 'I would love this item!'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                assert b'Your interest has been recorded' in response.data
                
                # Verify owner received in-app message
                notification = Message.query.filter_by(
                    sender_id=requester.id,
                    recipient_id=owner.id,
                    item_id=giveaway.id
                ).first()
                assert notification is not None
                assert notification.body == 'I would love this item!'

                # Verify email was sent with created message
                mock_email.assert_called_once()
                assert mock_email.call_args[0][0].id == notification.id


class TestGiveawayReleaseEmail:
    """Test email notifications on release-to-all."""
    
    def test_previous_recipient_notified_on_release(self, client, app, auth_user):
        """Test that previous recipient receives both message and email when giveaway is released."""
        with app.app_context():
            owner = auth_user()
            previous_recipient = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=previous_recipient
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=previous_recipient.id,
                status='selected'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.return_value = True
                
                response = client.post(f'/item/{giveaway.id}/release-to-all', follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify message was created for previous recipient about release
                release_message = Message.query.filter_by(
                    recipient_id=previous_recipient.id,
                    item_id=giveaway.id
                ).order_by(Message.timestamp.desc()).first()
                assert release_message is not None
                assert "released" in release_message.body.lower()
                
                # Verify email was sent to previous recipient
                assert mock_email.called
                email_recipients = [call[0][0].recipient_id for call in mock_email.call_args_list]
                assert previous_recipient.id in email_recipients
    
    def test_no_email_sent_to_other_interested_users_on_release(self, client, app, auth_user):
        """Test that other interested users don't get email on release-to-all."""
        with app.app_context():
            owner = auth_user()
            previous_recipient = UserFactory()
            other_user = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=previous_recipient
            )
            
            # Previous recipient's interest
            prev_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=previous_recipient.id,
                status='selected'
            )
            db.session.add(prev_interest)
            
            # Other user's interest - still active
            other_interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=other_user.id,
                status='active'
            )
            db.session.add(other_interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.return_value = True
                
                response = client.post(f'/item/{giveaway.id}/release-to-all', follow_redirects=True)
                
                assert response.status_code == 200
                
                # Check messages created
                messages = Message.query.filter_by(item_id=giveaway.id).all()
                recipient_ids = [m.recipient_id for m in messages]
                
                # Only previous recipient should receive a message, not the other interested user
                assert previous_recipient.id in recipient_ids
                # Note: other_user might already have messages from prior tests,
                # so we verify that no NEW release message went to them
                release_messages_to_other = [m for m in messages 
                                             if m.recipient_id == other_user.id 
                                             and 'released' in m.body.lower()]
                assert len(release_messages_to_other) == 0


class TestGiveawayHandoffNoEmail:
    """Test that confirm-handoff doesn't send additional emails."""
    
    def test_no_email_on_confirm_handoff(self, client, app, auth_user):
        """Test that no additional email is sent when owner confirms handoff."""
        with app.app_context():
            owner = auth_user()
            recipient = UserFactory()
            category = CategoryFactory()
            
            giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='pending_pickup',
                claimed_by=recipient
            )
            
            interest = GiveawayInterest(
                item_id=giveaway.id,
                user_id=recipient.id,
                status='selected'
            )
            db.session.add(interest)
            db.session.commit()
            
            login_user(client, owner.email)
            
            with patch('app.main.routes.send_message_notification_email') as mock_email:
                mock_email.return_value = True
                
                response = client.post(f'/item/{giveaway.id}/confirm-handoff', follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify email was NOT called for handoff confirmation
                assert not mock_email.called
                
                # Verify handoff was successful
                db.session.refresh(giveaway)
                assert giveaway.claim_status == 'claimed'
                assert giveaway.claimed_at is not None
