# FAMU backend

Real OTP login (valid 35 seconds) and the friendship kundali API.

## Run
    pip install -r requirements.txt
    export JWT_SECRET="long-random-string"
    export DEV_MODE=1            # local testing only, prints the OTP in the console
    uvicorn main:app --reload

Then open http://localhost:8000 : the FAMU page is served by the backend (static/index.html), so sign-in and scoring use the real API.

## Try the API directly
    curl -X POST localhost:8000/auth/send-otp -H "content-type: application/json" -d '{"identifier":"+919876543210"}'
    curl -X POST localhost:8000/auth/verify   -H "content-type: application/json" -d '{"identifier":"+919876543210","otp":"123456"}'
    curl -X POST localhost:8000/compare -H "authorization: Bearer TOKEN" -H "content-type: application/json" \
      -d '{"dob1":"1998-05-14","place1":"Hyderabad, India","dob2":"1999-11-02","place2":"Mumbai, India"}'

## Before going live
- Remove DEV_MODE, set Twilio (phone) and SMTP (email) variables, serve over HTTPS.
- Replace the in-memory OTP store with Redis so it works across servers.
- Google and Apple sign-in: add Firebase Authentication or OAuth, then exchange its token for a FAMU token.
- Nominatim (place lookup) allows about 1 request per second; use a paid geocoder at scale.

## Google and Apple sign-in (Firebase)
1. Create a project at console.firebase.google.com, then add a Web app and copy its config into `static/firebase-config.js`.
2. Authentication > Sign-in method: enable Google. For Apple, enable Apple and add your Apple Developer details (Services ID, Team ID, key). Apple needs a paid developer account.
3. Authentication > Settings > Authorized domains: add the domain where you host FAMU (localhost works for testing).
4. Set `FIREBASE_PROJECT_ID` on the backend (same project ID), restart, and the Google and Apple buttons will work.
Phone and email OTP keep working without Firebase.
