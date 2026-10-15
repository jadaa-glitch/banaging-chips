from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from app.database import get_db, query_db

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    if 'user_id' in session:
        return query_db(
            'SELECT user_id, full_name, username, role, is_verified FROM users WHERE user_id = %s',
            (session['user_id'],),
            one=True
        )
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))
        
        user = query_db('SELECT * FROM users WHERE username = %s', (username,), one=True)
        if user and check_password_hash(user['password_hash'], password):
            if not user.get('is_verified', 1):
                error = 'Account is pending store manager verification.'
            else:
                session.clear()
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                session['role'] = user.get('role', 'Cashier / Sales Clerk')
                if remember:
                    session.permanent = True
                return redirect(url_for('dashboard.index'))
        else:
            error = 'Invalid username or password. Please try again.'
            
    return render_template('login.html', error=error)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    error = None
    success = None
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', 'Cashier / Sales Clerk').strip()
        
        if not full_name or not username or not password:
            error = 'All required fields must be completed.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters long.'
        else:
            existing = query_db('SELECT user_id FROM users WHERE username = %s', (username,), one=True)
            if existing:
                error = f'Username @{username} is already taken.'
            else:
                pwd_hash = generate_password_hash(password)
                db = get_db()
                with db.cursor() as cur:
                    cur.execute('''
                        INSERT INTO users (full_name, username, password_hash, role, is_verified)
                        VALUES (%s, %s, %s, %s, 1)
                    ''', (full_name, username, pwd_hash, role))
                    db.commit()
                flash('Account created successfully! Please sign in.', 'success')
                return redirect(url_for('auth.login'))
                
    return render_template('register.html', error=error, success=success)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
