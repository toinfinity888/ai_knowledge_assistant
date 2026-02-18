from flask import Blueprint, render_template, request, redirect, url_for, session, make_response
from app.core.rag_singleton import rag_engine
from app.models.query import Query
import os
from app.logging.logger import logger
from app.logging.logging_service import user_query_logging
from app.services.auth_service import get_auth_service
from app.services.audit_service import get_audit_service
from app.models.audit_log import ActionType, TargetType
from app.database.postgresql_session import get_db_session
import time

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
front = Blueprint("front", __name__, template_folder=template_dir)


@front.route("/login", methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    error = None
    email = ''
    message = request.args.get('message')

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            error = 'Please enter both email and password'
        else:
            auth_service = get_auth_service()

            with get_db_session() as db:
                user = auth_service.authenticate(email, password, db)

                if user:
                    # Check if company is active (skip for SUPER_ADMIN who has no company)
                    if user.is_super_admin():
                        # SUPER_ADMIN has no company - proceed with login
                        pass
                    elif not user.company or not user.company.is_active:
                        error = 'Your company account is inactive'

                    if not error:
                        # Create tokens
                        access_token = auth_service.create_access_token(user)
                        device_info = request.headers.get('User-Agent', '')[:500]
                        ip_address = request.remote_addr
                        refresh_token, _ = auth_service.create_refresh_token(
                            user, db, device_info=device_info, ip_address=ip_address
                        )

                        # Store tokens in session/cookies
                        session['user_id'] = user.id
                        session['user_email'] = user.email
                        session['user_name'] = user.full_name
                        session['company_id'] = user.company_id
                        session['company_name'] = user.company.name if user.company else 'Platform'
                        session['role'] = user.role.value

                        # Set tokens as cookies for API calls
                        response = make_response(redirect(url_for('front.index')))
                        response.set_cookie(
                            'access_token', access_token,
                            httponly=True, secure=False, samesite='Lax',
                            max_age=auth_service.settings.access_token_ttl
                        )
                        response.set_cookie(
                            'refresh_token', refresh_token,
                            httponly=True, secure=False, samesite='Lax',
                            max_age=auth_service.settings.refresh_token_ttl
                        )

                        # Audit log for successful login
                        audit_service = get_audit_service()
                        audit_service.log_action(
                            action_type=ActionType.AUTH_LOGIN,
                            target_type=TargetType.SESSION,
                            target_id=user.id,
                            actor_user_id=user.id,
                            actor_email=user.email,
                            company_id=user.company_id,
                            details={"method": "web"},
                            ip_address=request.remote_addr,
                            user_agent=request.headers.get('User-Agent', '')[:500],
                            db=db,
                        )
                        db.commit()

                        logger.info(f"User logged in via web: {user.email}")
                        return response
                else:
                    error = 'Invalid email or password'

    return render_template('login.html', error=error, email=email, message=message)


@front.route("/logout")
def logout():
    """Logout and clear session"""
    # Capture user info before clearing session
    user_id = session.get('user_id')
    user_email = session.get('user_email', 'unknown')
    company_id = session.get('company_id')

    with get_db_session() as db:
        # Revoke refresh token if present
        refresh_token = request.cookies.get('refresh_token')
        if refresh_token:
            auth_service = get_auth_service()
            auth_service.revoke_refresh_token(refresh_token, db)

        # Audit log for logout
        if user_id:
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type=ActionType.AUTH_LOGOUT,
                target_type=TargetType.SESSION,
                target_id=user_id,
                actor_user_id=user_id,
                actor_email=user_email,
                company_id=company_id,
                details={"method": "web"},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:500],
                db=db,
            )
        db.commit()

    # Clear session
    session.clear()

    # Clear cookies
    response = make_response(redirect(url_for('front.login', message='You have been logged out')))
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')

    return response

@front.route("/", methods=['GET'])
def index():
    """Home page - redirect to technician support console (requires login)"""
    # Check if user is logged in
    if not session.get('user_id'):
        return redirect(url_for('front.login'))

    return render_template('demo/technician_support.html')


@front.route("/rag", methods=['GET', 'POST'])
def rag_assistant():
    """RAG Assistant page for testing queries"""
    answer = ''
    retrieved_context = []
    if request.method == 'POST':
        query_text = request.form['query']

        start = time.time()
        answer, retrieved_context = rag_engine.ask(Query(text=query_text))
        if not answer:
            logger.info('RAG Engine no have an answer')
        end = time.time()
        response_time_ms = (end - start) * 1000

        has_response = bool(answer and answer.strip())
        llm_model_used = rag_engine.get_llm_model_name()
        retriever_used = rag_engine.get_search_engine_name()

        user_query_logging(
            query_text=query_text,
            response_text=answer,
            has_response=has_response,
            response_status='OK', # May be extended in future
            response_time_ms=response_time_ms,
            retriever_used=retriever_used,
            llm_model_used=llm_model_used,
            retrieved_context=retrieved_context,
        )

    return render_template('index.html', answer=answer, retrieved_context=retrieved_context)


@front.route("/account", methods=['GET', 'POST'])
def account_settings():
    """Account settings page - redirect to admin panel settings"""
    # Check if user is logged in
    if not session.get('user_id'):
        return redirect(url_for('front.login'))

    # Redirect to the new admin panel settings page
    return redirect(url_for('admin_panel.settings'))


@front.route("/accept-invite", methods=['GET', 'POST'])
def accept_invite():
    """Accept invitation and create user account"""
    from app.services.invitation_service import (
        get_invitation_service,
        InvitationNotFoundError,
        InvitationExpiredError,
        InvitationAlreadyAcceptedError,
        InvitationError,
    )

    token = request.args.get('token', '') or request.form.get('token', '')
    error = None
    form_error = None
    invitation = None
    full_name = ''

    if not token:
        return render_template('accept_invite.html', error='No invitation token provided')

    auth_service = get_auth_service()

    with get_db_session() as db:
        invitation_service = get_invitation_service()

        # GET: Validate and show form
        if request.method == 'GET':
            inv = invitation_service.get_invitation_by_token(token, db)

            if not inv:
                return render_template('accept_invite.html', error='Invalid invitation link')

            if inv.is_accepted:
                return render_template('accept_invite.html', error='This invitation has already been used')

            if inv.is_expired():
                return render_template('accept_invite.html', error='This invitation has expired')

            invitation = {
                'token': token,
                'email': inv.email,
                'role': inv.role.value.replace('_', ' '),
                'company_name': inv.company.name if inv.company else None,
            }

            return render_template('accept_invite.html', invitation=invitation)

        # POST: Accept invitation
        if request.method == 'POST':
            full_name = request.form.get('full_name', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            # Validate form
            if not full_name:
                form_error = 'Full name is required'
            elif not password:
                form_error = 'Password is required'
            elif len(password) < 8:
                form_error = 'Password must be at least 8 characters'
            elif password != confirm_password:
                form_error = 'Passwords do not match'

            if form_error:
                # Re-fetch invitation for form display
                inv = invitation_service.get_invitation_by_token(token, db)
                if inv:
                    invitation = {
                        'token': token,
                        'email': inv.email,
                        'role': inv.role.value.replace('_', ' '),
                        'company_name': inv.company.name if inv.company else None,
                    }
                return render_template(
                    'accept_invite.html',
                    invitation=invitation,
                    form_error=form_error,
                    full_name=full_name
                )

            try:
                # Accept the invitation
                device_info = request.headers.get('User-Agent', '')[:500]
                ip_address = request.remote_addr

                user, access_token, refresh_token = invitation_service.accept_invitation(
                    token=token,
                    password=password,
                    full_name=full_name,
                    db=db,
                    ip_address=ip_address,
                    user_agent=device_info
                )
                db.commit()

                # Log the user in
                session['user_id'] = user.id
                session['user_email'] = user.email
                session['user_name'] = user.full_name
                session['company_id'] = user.company_id
                session['company_name'] = user.company.name if user.company else 'Platform'
                session['role'] = user.role.value

                # Set tokens as cookies
                response = make_response(redirect(url_for('front.index')))
                response.set_cookie(
                    'access_token', access_token,
                    httponly=True, secure=False, samesite='Lax',
                    max_age=auth_service.settings.access_token_ttl
                )
                response.set_cookie(
                    'refresh_token', refresh_token,
                    httponly=True, secure=False, samesite='Lax',
                    max_age=auth_service.settings.refresh_token_ttl
                )

                logger.info(f"User accepted invitation and logged in: {user.email}")
                return response

            except InvitationNotFoundError:
                error = 'Invalid invitation link'
            except InvitationExpiredError:
                error = 'This invitation has expired'
            except InvitationAlreadyAcceptedError:
                error = 'This invitation has already been used'
            except InvitationError as e:
                error = str(e)
            except ValueError as e:
                # Re-fetch invitation for form display
                inv = invitation_service.get_invitation_by_token(token, db)
                if inv:
                    invitation = {
                        'token': token,
                        'email': inv.email,
                        'role': inv.role.value.replace('_', ' '),
                        'company_name': inv.company.name if inv.company else None,
                    }
                return render_template(
                    'accept_invite.html',
                    invitation=invitation,
                    form_error=str(e),
                    full_name=full_name
                )
            except Exception as e:
                logger.error(f"Error accepting invitation: {e}")
                error = 'An error occurred. Please try again.'

    return render_template('accept_invite.html', error=error)