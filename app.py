from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Use instance folder for database
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'email.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    payment_verified = db.Column(db.Boolean, default=False)
    subscription_start = db.Column(db.DateTime)
    subscription_end = db.Column(db.DateTime)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(120), nullable=False)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    thread_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]), lazy=True)

# ---------- ROUTES ----------
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if not email.endswith('@speedmail.com'):
            flash('Email must end with @speedmail.com', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Account already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        new_user = User(email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Registered successfully! Please login and pay to activate.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('User does not exist', 'danger')
            return redirect(url_for('login'))
        if check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Logged in successfully', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', user=user)

# ---------- Payment ----------
@app.route('/payment/<int:user_id>')
def payment(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get_or_404(user_id)
    return render_template('payment.html', user=user)

# ---------- Admin ----------
@app.route('/admin/pending')
def admin_pending():
    # Admin check placeholder
    pending_users = User.query.filter_by(is_active=False).all()
    return render_template('admin_pending.html', pending_users=pending_users)

@app.route('/admin/approve/<int:user_id>')
def admin_approve(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = True
    user.payment_verified = True
    user.subscription_start = datetime.utcnow()
    user.subscription_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    flash(f'User {user.email} approved.', 'success')
    return redirect(url_for('admin_pending'))

# ---------- RUN ----------
if __name__ == '__main__':
    os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
