# Put FAMU online (Render, free tier works for testing)

1. Create a GitHub repository and upload the contents of this folder.
2. On render.com choose New > Blueprint, connect the repository. It reads `render.yaml` and builds the Dockerfile.
3. Fill the environment variables Render asks for:
   - Phone OTP: TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM
   - Email OTP: SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM
   - Google/Apple sign-in: FIREBASE_PROJECT_ID (and the config in static/firebase-config.js)
   JWT_SECRET is generated for you. Never set DEV_MODE online.
4. Open the URL Render gives you (https://famu.onrender.com or similar). Add that domain in Firebase > Authentication > Settings > Authorized domains.

Important:
- Run one instance only. OTPs are kept in memory; for several instances switch the OTP store to Redis.
- The free plan sleeps when idle, so the first visit can take about a minute.
- Place lookup uses free Nominatim (about 1 request per second). Use a paid geocoder if many people use FAMU.
- Other hosts work too (Railway, Fly.io, any VPS): the Dockerfile runs anywhere.
