"""
FAMU backend: OTP login (35 s expiry) + friendship kundali API.

Run:  uvicorn main:app --reload
"""
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import time
from email.message import EmailMessage

import httpx
import jwt
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token as google_id_token
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from friendship_kundali import compare

OTP_TTL = 35          # seconds an OTP stays valid
MAX_TRIES = 5         # wrong guesses before the OTP is destroyed
MAX_SENDS_PER_HOUR = 5
SECRET = os.environ["JWT_SECRET"]   # required: long random string
DEV_MODE = os.environ.get("DEV_MODE") == "1"  # prints OTP to console, never use in production

# NOTE: in-memory store. Use Redis (SETEX key 35 ...) when running more than one server.
OTPS = {}    # identifier -> {"h": hash, "exp": ts, "tries": n}
SENDS = {}   # identifier -> [timestamps]

app = FastAPI(title="FAMU")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else [],
    allow_methods=["*"], allow_headers=["*"],
)
bearer = HTTPBearer()


def normalize(identifier: str):
    v = identifier.strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
        return v.lower(), "email"
    p = re.sub(r"[ ()-]", "", v)
    if re.fullmatch(r"\+[0-9]{8,15}", p):
        return p, "phone"
    raise HTTPException(400, "Enter an email or a phone number with country code, like +919876543210")


def digest(identifier, otp):
    return hmac.new(SECRET.encode(), f"{identifier}:{otp}".encode(), hashlib.sha256).hexdigest()


def deliver(identifier, kind, otp):
    msg = f"Your FAMU code is {otp}. It expires in {OTP_TTL} seconds."
    if DEV_MODE:
        print(f"[DEV] OTP for {identifier}: {otp}")
        return
    if kind == "phone":
        sid, tok, frm = (os.environ.get(k) for k in ("TWILIO_SID", "TWILIO_TOKEN", "TWILIO_FROM"))
        if not (sid and tok and frm):
            raise HTTPException(503, "SMS is not configured")
        r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                       auth=(sid, tok), data={"From": frm, "To": identifier, "Body": msg}, timeout=10)
        if r.status_code >= 300:
            raise HTTPException(502, "Could not send SMS")
    else:
        host = os.environ.get("SMTP_HOST")
        if not host:
            raise HTTPException(503, "Email is not configured")
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = os.environ["SMTP_FROM"], identifier, "Your FAMU code"
        m.set_content(msg)
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587))) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            s.send_message(m)


class SendReq(BaseModel):
    identifier: str


class VerifyReq(BaseModel):
    identifier: str
    otp: str


@app.post("/auth/send-otp")
def send_otp(req: SendReq):
    ident, kind = normalize(req.identifier)
    now = time.time()
    recent = [t for t in SENDS.get(ident, []) if now - t < 3600]
    if len(recent) >= MAX_SENDS_PER_HOUR:
        raise HTTPException(429, "Too many codes requested. Try again later.")
    cur = OTPS.get(ident)
    if cur and cur["exp"] > now:
        raise HTTPException(429, "A code was just sent. Wait until it expires.")
    otp = f"{secrets.randbelow(900000) + 100000}"
    deliver(ident, kind, otp)
    OTPS[ident] = {"h": digest(ident, otp), "exp": now + OTP_TTL, "tries": 0}
    SENDS[ident] = recent + [now]
    return {"sent": True, "expires_in": OTP_TTL}


@app.post("/auth/verify")
def verify(req: VerifyReq):
    ident, _ = normalize(req.identifier)
    rec = OTPS.get(ident)
    if not rec or rec["exp"] < time.time():
        OTPS.pop(ident, None)
        raise HTTPException(400, "OTP expired. Request a new one.")
    rec["tries"] += 1
    if not hmac.compare_digest(rec["h"], digest(ident, req.otp.strip())):
        if rec["tries"] >= MAX_TRIES:
            OTPS.pop(ident, None)
        raise HTTPException(400, "Incorrect OTP.")
    OTPS.pop(ident, None)
    token = jwt.encode({"sub": ident, "exp": int(time.time()) + 7 * 86400}, SECRET, algorithm="HS256")
    return {"token": token}


class FirebaseReq(BaseModel):
    id_token: str


@app.post("/auth/firebase")
def firebase_login(req: FirebaseReq):
    """Google / Apple sign-in: verify the Firebase ID token, then issue a FAMU token."""
    project = os.environ.get("FIREBASE_PROJECT_ID")
    if not project:
        raise HTTPException(503, "Google and Apple sign-in are not configured")
    try:
        claims = google_id_token.verify_firebase_token(req.id_token, g_requests.Request(), audience=project)
    except Exception:
        claims = None
    if not claims:
        raise HTTPException(401, "Sign-in could not be verified.")
    if claims.get("email") and not claims.get("email_verified"):
        raise HTTPException(401, "Your email is not verified.")
    ident = (claims.get("email") or claims["sub"]).lower()
    token = jwt.encode({"sub": ident, "exp": int(time.time()) + 7 * 86400}, SECRET, algorithm="HS256")
    return {"token": token}


def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        return jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Please sign in again.")


class CompareReq(BaseModel):
    dob1: str
    place1: str
    dob2: str
    place2: str


@app.post("/compare")
def compare_route(req: CompareReq, user: str = Depends(current_user)):
    try:
        return compare(req.dob1, req.place1, req.dob2, req.place2)
    except ValueError as e:
        raise HTTPException(400, str(e))


# Serves the FAMU web page at "/". Keep this last so it does not shadow the API routes.
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
