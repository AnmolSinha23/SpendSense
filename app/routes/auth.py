"""
SpendSense - Authentication Routes
Handles user registration, login, and logout using session-based authentication
and Werkzeug secure password hashing (scrypt).
"""

from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import query_db, get_db

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """
    Decorator that enforces session authentication for protected views.
    Redirects unauthenticated users to the login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access SpendSense.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles new user registration.
    Inserts credentials into `users` table and creates initial starter accounts.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Basic validations
        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template('auth/register.html', name=name, email=email)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/register.html', name=name, email=email)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('auth/register.html', name=name, email=email)

        # Check if email is already taken (Unique constraint check)
        existing_user = query_db(
            "SELECT user_id FROM users WHERE email = %s",
            (email,),
            one=True
        )
        if existing_user:
            flash("An account with this email address already exists. Please log in.", "warning")
            return redirect(url_for('auth.login'))

        # Secure password hashing using Werkzeug
        hashed_password = generate_password_hash(password)

        try:
            # Atomic user creation and default account setup
            db = get_db()
            cursor = db.cursor(dictionary=True)

            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, hashed_password)
            )
            new_user_id = cursor.lastrowid

            # Create default starter accounts for every new user
            cursor.execute(
                "INSERT INTO accounts (user_id, account_name, account_type, balance) VALUES "
                "(%s, 'Cash Wallet', 'Cash', 0.00), "
                "(%s, 'Main Bank Account', 'Bank', 0.00)",
                (new_user_id, new_user_id)
            )

            db.commit()
            cursor.close()

            # Automatically log the user in
            session['user_id'] = new_user_id
            session['user_name'] = name
            session['user_email'] = email

            flash(f"Welcome to SpendSense, {name}! Your account has been initialized.", "success")
            return redirect(url_for('dashboard.index'))

        except Exception as e:
            flash(f"Error registering user: {str(e)}", "danger")
            return render_template('auth/register.html', name=name, email=email)

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Authenticates user credentials against the database.
    Sets session on successful password verification.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template('auth/login.html', email=email)

        # Retrieve user record by email
        user = query_db(
            "SELECT user_id, name, email, password_hash FROM users WHERE email = %s",
            (email,),
            one=True
        )

        if user and user['password_hash'] and check_password_hash(user['password_hash'], password):
            pending_sub = session.get('pending_google_sub')
            
            session.clear()
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']

            if pending_sub:
                query_db("UPDATE users SET google_sub = %s WHERE user_id = %s", (pending_sub, user['user_id']), commit=True)
                flash(f"Welcome back, {user['name']}! Your Google account has been successfully linked.", "success")
            else:
                flash(f"Welcome back, {user['name']}!", "success")
                
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard.index'))
        else:
            if user and not user['password_hash']:
                flash("This email is associated with a Google account. Please use 'Continue with Google'.", "warning")
            else:
                flash("Invalid email or password. Please try again.", "danger")
            return render_template('auth/login.html', email=email)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """
    Terminates the user's active session.
    """
    user_name = session.get('user_name', 'User')
    session.clear()
    flash(f"Goodbye, {user_name}. You have been securely logged out.", "info")
    return redirect(url_for('auth.login'))


@auth_bp.route('/auth/google/login')
def google_login():
    next_url = request.args.get('next')
    if next_url:
        session['next_url'] = next_url
    redirect_uri = url_for('auth.google_callback', _external=True)
    return current_app.oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/auth/google/callback')
def google_callback():
    try:
        token = current_app.oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            flash("Failed to retrieve user information from Google.", "danger")
            return redirect(url_for('auth.login'))
            
        google_sub = user_info.get('sub')
        email = user_info.get('email', '').strip().lower()
        name = user_info.get('name', 'Google User').strip()
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE google_sub = %s", (google_sub,))
        user = cursor.fetchone()
        
        if user:
            session.clear()
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            flash(f"Welcome back, {user['name']}!", "success")
        else:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                if not existing_user['password_hash']:
                    flash("This email is already associated with a different Google account. Please log in with the correct Google account.", "danger")
                else:
                    flash("An account with this email already exists. Please log in with your password to link your Google account.", "warning")
                    session['pending_google_sub'] = google_sub
                return redirect(url_for('auth.login'))
            else:
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, google_sub) VALUES (%s, %s, %s, %s)",
                    (name, email, None, google_sub)
                )
                new_user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO accounts (user_id, account_name, account_type, balance) VALUES "
                    "(%s, 'Cash Wallet', 'Cash', 0.00), "
                    "(%s, 'Main Bank Account', 'Bank', 0.00)",
                    (new_user_id, new_user_id)
                )
                db.commit()
                session.clear()
                session['user_id'] = new_user_id
                session['user_name'] = name
                session['user_email'] = email
                flash(f"Welcome to SpendSense, {name}! Your account has been initialized via Google.", "success")
        cursor.close()
        
        next_url = session.pop('next_url', None)
        return redirect(next_url or url_for('dashboard.index'))
    except Exception as e:
        flash(f"Google authentication failed. Please try again.", "danger")
        return redirect(url_for('auth.login'))
