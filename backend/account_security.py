"""Account security helpers shared with the existing Flask app.

Requires SECRET_KEY, MONGO_URI, and real SMTP credentials for account actions.
Never return verification/reset tokens to the browser.
"""
import os
import re
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

from flask import jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pymongo import ReturnDocument

from models import create_user, format_user, get_user_by_email
from security import generate_token, hash_password, hash_token, verify_password

TOKEN_LIFETIME_SECONDS = 12 * 60 * 60
PASSWORD_MIN_LENGTH = 12
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def utcnow():
    return datetime.now(timezone.utc)


def serializer():
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32 or secret.startswith("change_me"):
        raise RuntimeError("Set SECRET_KEY in backend/.env to a random value (32+ characters).")
    return URLSafeTimedSerializer(secret, salt="cinema-login-v1")


def make_access_token(user):
    return serializer().dumps({"uid": user["userId"], "v": user.get("sessionVersion", 0)})


def read_authenticated_user(users):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = serializer().loads(header[7:].strip(), max_age=TOKEN_LIFETIME_SECONDS)
    except (ValueError, BadSignature, SignatureExpired, RuntimeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("uid"), str):
        return None
    user = users.find_one({"userId": payload["uid"]}, {"_id": 0})
    if not user or user.get("status") != "Active":
        return None
    if payload.get("v") != user.get("sessionVersion", 0):
        return None
    return user


def require_owner(users, user_id):
    user = read_authenticated_user(users)
    if user is None:
        return jsonify({"error": "Sign in to access your account."}), 401
    if user["userId"] != user_id:
        return jsonify({"error": "You may only access your own account."}), 403
    return None


def smtp_ready():
    return (all(os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))
            and "your_" not in os.getenv("SMTP_USER", "")
            and "your_" not in os.getenv("SMTP_PASSWORD", ""))


def deliver_link(to_address, subject, page, token):
    if not smtp_ready():
        raise RuntimeError("SMTP configuration is missing; ask your team to configure email delivery.")
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    link = f"{frontend}/account/{page}?{urlencode({'token': token})}"
    mail = EmailMessage()
    mail["From"] = os.getenv("SMTP_USER")
    mail["To"] = to_address
    mail["Subject"] = subject
    mail.set_content(f"Use this link to continue your Cinema account request:\n\n{link}\n\nIf this wasn't you, ignore this message.")
    port = int(os.getenv("SMTP_PORT", "587"))
    if port == 465:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=12) as smtp:
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(mail)
    else:
        with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=12) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(mail)


def issue_email_token(tokens, user, kind, duration, page, subject):
    raw = generate_token()
    record = {
        "tokenHash": hash_token(raw), "userId": user["userId"],
        "type": kind, "expiresAt": utcnow() + duration, "used": False
    }
    result = tokens.insert_one(record)
    try:
        deliver_link(user["email"], subject, page, raw)
    except Exception:
        tokens.delete_one({"_id": result.inserted_id})
        raise


def consume_token(tokens, raw, kind):
    if not isinstance(raw, str) or not raw or len(raw) > 1024:
        return None
    return tokens.find_one_and_update(
        {"tokenHash": hash_token(raw), "type": kind, "used": False,
         "expiresAt": {"$gt": utcnow()}},
        {"$set": {"used": True}},
        return_document=ReturnDocument.BEFORE,
    )


def valid_password(password):
    return isinstance(password, str) and PASSWORD_MIN_LENGTH <= len(password) <= 128


def registration(users, tokens):
    data = request.get_json(silent=True) or {}
    names = [data.get("first_name"), data.get("last_name")]
    email = data.get("email")
    phone = data.get("phone", "")
    password = data.get("password")
    if not all(isinstance(x, str) and 1 <= len(x.strip()) <= 80 for x in names):
        return jsonify({"error": "Provide a first and last name (up to 80 characters each)."}), 400
    if not isinstance(email, str) or len(email) > 254 or not EMAIL_RE.fullmatch(email.strip()):
        return jsonify({"error": "Provide a valid email address."}), 400
    if not isinstance(phone, str) or len(phone) > 30:
        return jsonify({"error": "Phone number must be 30 characters or fewer."}), 400
    if not valid_password(password):
        return jsonify({"error": "Password must be between 12 and 128 characters."}), 400
    if not smtp_ready():
        return jsonify({"error": "Email delivery is not configured. Contact the project administrator."}), 503
    user = create_user(users, names[0], names[1], email, phone, password, data.get("promo_opt_in") is True)
    if user is None:
        return jsonify({"error": "An account with this email already exists."}), 409
    try:
        issue_email_token(tokens, user, "verify", timedelta(hours=24), "verify", "Verify your Cinema account")
    except Exception as e:
        print("SMTP ERROR:", repr(e)) # remove later
        return jsonify({"error": "Account created, but verification email could not be delivered. Use Resend verification."}), 503
    return jsonify({"message": "Account created. Check your email to verify your account.", "status": "Inactive"}), 201


def resend_verification(users, tokens):
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    if not isinstance(email, str) or len(email) > 254:
        return jsonify({"error": "Invalid email."}), 400
    message = {"message": "If an unverified account exists, a verification link will be sent."}
    user = get_user_by_email(users, email)
    if user and user.get("status") == "Inactive":
        if not smtp_ready():
            return jsonify({"error": "Email delivery is not configured."}), 503
        try:
            issue_email_token(tokens, user, "verify", timedelta(hours=24), "verify", "Verify your Cinema account")
        except Exception:
            return jsonify({"error": "Unable to deliver verification email."}), 503
    return jsonify(message), 200


def verify_registration(users, tokens):
    data = request.get_json(silent=True) or {}
    raw = data.get("token") if request.method == "POST" else request.args.get("token")
    record = consume_token(tokens, raw, "verify")
    if record is None:
        return jsonify({"error": "Verification link is invalid, expired, or already used."}), 400
    result = users.update_one({"userId": record["userId"], "status": "Inactive"}, {"$set": {"status": "Active"}})
    if result.matched_count != 1:
        return jsonify({"error": "Account unavailable or already verified."}), 400
    return jsonify({"message": "Account verified. You may sign in."}), 200


def forgot_password(users, tokens):
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    if not isinstance(email, str) or len(email) > 254:
        return jsonify({"error": "Invalid email."}), 400
    message = {"message": "If the account exists, a reset link will be sent."}
    user = get_user_by_email(users, email)
    if user:
        if not smtp_ready():
            return jsonify({"error": "Email delivery is not configured."}), 503
        try:
            issue_email_token(tokens, user, "reset", timedelta(hours=1), "reset-password", "Reset your Cinema password")
        except Exception:
            return jsonify({"error": "Unable to deliver reset email."}), 503
    return jsonify(message), 200


def reset_password(users, tokens):
    data = request.get_json(silent=True) or {}
    password = data.get("new_password")
    if not valid_password(password):
        return jsonify({"error": "New password must be 12–128 characters."}), 400
    record = consume_token(tokens, data.get("token"), "reset")
    if record is None:
        return jsonify({"error": "Reset link is invalid, expired, or already used."}), 400
    result = users.update_one({"userId": record["userId"]}, {
        "$set": {"passwordHash": hash_password(password)}, "$inc": {"sessionVersion": 1}
    })
    if result.matched_count != 1:
        return jsonify({"error": "Account no longer exists."}), 404
    return jsonify({"message": "Password updated. Sign in with your new password."}), 200


def change_password(users, user_id):
    user = read_authenticated_user(users)
    if user is None or user["userId"] != user_id:
        return jsonify({"error": "Unauthorized."}), 401
    data = request.get_json(silent=True) or {}
    current = data.get("current_password", "")
    new = data.get("new_password", "")
    if not valid_password(new):
        return jsonify({"error": "New password must be 12–128 characters."}), 400
    if not isinstance(current, str) or not verify_password(current, user.get("passwordHash", "")):
        return jsonify({"error": "Current password is incorrect."}), 400
    if verify_password(new, user["passwordHash"]):
        return jsonify({"error": "Choose a different password."}), 400
    users.update_one({"userId": user_id}, {
        "$set": {"passwordHash": hash_password(new)}, "$inc": {"sessionVersion": 1}
    })
    return jsonify({"message": "Password changed. Please sign in again."}), 200
