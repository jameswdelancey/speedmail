import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
env_secret_key = os.environ.get("SPEEDMAIL_SECRET_KEY")
if not env_secret_key:
    env_secret_key = os.environ.get("SECRET_KEY")
app.config["SECRET_KEY"] = env_secret_key or os.urandom(24).hex()

# Use instance folder for database
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, "instance")
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, "email.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# ---------- MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
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
    thread_id = db.Column(db.Integer, db.ForeignKey("message.id"), nullable=True)
    replies = db.relationship(
        "Message", backref=db.backref("parent", remote_side=[id]), lazy=True
    )


# ---------- ROUTES ----------
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


def _get_current_user():
    if "user_id" not in session:
        return None
    return db.session.get(User, session["user_id"])


def _require_admin() -> Optional[User]:
    user = _get_current_user()
    if user is None:
        flash("Please log in to access admin tools.", "warning")
        return None
    if not user.is_admin:
        abort(403)
    return user


def _validate_csrf() -> bool:
    form_token = request.form.get("csrf_token")
    session_token = session.get("_csrf_token")
    if not form_token or not session_token:
        return False
    try:
        return secrets.compare_digest(form_token, session_token)
    except Exception:
        return False


def _get_or_create_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = _get_or_create_csrf_token


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not _validate_csrf():
            flash("Invalid session token. Please try again.", "danger")
            return redirect(url_for("register"))
        email = request.form["email"]
        password = request.form["password"]

        if not email.endswith("@speedmail.com"):
            flash("Email must end with @speedmail.com", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Account already exists.", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        new_user = User(email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash("Registered successfully! Please login and pay to activate.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not _validate_csrf():
            flash("Invalid session token. Please try again.", "danger")
            return redirect(url_for("login"))
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("User does not exist", "danger")
            return redirect(url_for("login"))
        if check_password_hash(user.password, password):
            if not user.is_active or not user.payment_verified:
                flash(
                    "Your account is not active. Please contact support for assistance.",
                    "warning",
                )
                return redirect(url_for("login"))
            if user.subscription_end and user.subscription_end < datetime.utcnow():
                flash(
                    "Your subscription has expired. Please renew to continue.",
                    "warning",
                )
                return redirect(url_for("login"))
            session["user_id"] = user.id
            flash("Logged in successfully", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = _get_current_user()
    if not user:
        return redirect(url_for("login"))
    if not user.is_active or not user.payment_verified:
        flash("Your account is not active.", "warning")
        session.pop("user_id", None)
        return redirect(url_for("login"))
    if user.subscription_end and user.subscription_end < datetime.utcnow():
        flash("Your subscription has expired.", "warning")
        session.pop("user_id", None)
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=user)


# ---------- Payment ----------
@app.route("/payment/<int:user_id>")
def payment(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    session_user = _get_current_user()
    if not session_user:
        return redirect(url_for("login"))
    if session_user.id != user_id and not session_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    return render_template("payment.html", user=user)


# ---------- Admin ----------
@app.route("/admin/pending")
def admin_pending():
    if _require_admin() is None:
        return redirect(url_for("login"))
    pending_users = User.query.filter_by(is_active=False).all()
    return render_template("admin_pending.html", pending_users=pending_users)


@app.route("/admin/approve/<int:user_id>")
def admin_approve(user_id):
    if _require_admin() is None:
        return redirect(url_for("login"))
    user = User.query.get_or_404(user_id)
    user.is_active = True
    user.payment_verified = True
    user.subscription_start = datetime.utcnow()
    user.subscription_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    flash(f"User {user.email} approved.", "success")
    return redirect(url_for("admin_pending"))


# ---------- RUN ----------
if __name__ == "__main__":
    os.makedirs(os.path.join(basedir, "instance"), exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
