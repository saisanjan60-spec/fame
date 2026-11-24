"""
Friendship Kundali - starter
Input : date of birth + place of birth (no birth time) for two people
Output: Moon sign, nakshatra, 36-point Guna score (scaled to 100), confidence

pip install pyswisseph geopy timezonefinder
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import lru_cache
from itertools import product

import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

swe.set_sid_mode(swe.SIDM_LAHIRI)

RASHIS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
          "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus",
         "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
              "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
              "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
              "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
              "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
              "Uttara Bhadrapada", "Revati"]

# ---------- location + Moon ----------
_geo = Nominatim(user_agent="friendship-kundali")
_tf = TimezoneFinder()


@lru_cache(maxsize=512)
def locate(place):
    loc = _geo.geocode(place)
    if not loc:
        raise ValueError(f"Place not found: {place}")
    tz = _tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
    return loc.latitude, loc.longitude, tz


def moon_lon(dt_utc):
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                    dt_utc.hour + dt_utc.minute / 60)
    return swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)[0][0]


def moon_info(lon):
    rashi = int(lon // 30)
    nak = int(lon // (360 / 27))
    return rashi, nak


def moon_options(dob, place):
    """dob = 'YYYY-MM-DD'. Returns (noon result, all possible (rashi, nak) in that day)."""
    _, _, tz = locate(place)
    y, m, d = map(int, dob.split("-"))
    start = datetime(y, m, d, 0, 0, tzinfo=ZoneInfo(tz))
    seen = set()
    for i in range(0, 48):  # every 30 min across the local day
        t = (start + timedelta(minutes=30 * i)).astimezone(timezone.utc)
        seen.add(moon_info(moon_lon(t)))
    noon = (start + timedelta(hours=12)).astimezone(timezone.utc)
    return moon_info(moon_lon(noon)), seen


# ---------- Guna Milan tables ----------
VARNA = {3: 4, 7: 4, 11: 4,   # Cancer, Scorpio, Pisces: Brahmin
         0: 3, 4: 3, 8: 3,    # Aries, Leo, Sagittarius: Kshatriya
         1: 2, 5: 2, 9: 2,    # Taurus, Virgo, Capricorn: Vaishya
         2: 1, 6: 1, 10: 1}   # Gemini, Libra, Aquarius: Shudra

# Vashya group per rashi (simplified to whole signs)
VASHYA_GROUP = {0: "C", 1: "C", 2: "M", 3: "J", 4: "V", 5: "M", 6: "M",
                7: "K", 8: "M", 9: "C", 10: "M", 11: "J"}
VASHYA_SCORE = {
    "C": {"C": 2, "M": 1, "J": 1, "V": 0.5, "K": 1},
    "M": {"C": 1, "M": 2, "J": 0.5, "V": 0, "K": 1},
    "J": {"C": 1, "M": 0.5, "J": 2, "V": 1, "K": 1},
    "V": {"C": 0, "M": 0, "J": 0, "V": 2, "K": 0},
    "K": {"C": 1, "M": 1, "J": 1, "V": 0, "K": 2},
}

YONI = ["Horse", "Elephant", "Sheep", "Serpent", "Serpent", "Dog", "Cat",
        "Sheep", "Cat", "Rat", "Rat", "Cow", "Buffalo", "Tiger", "Buffalo",
        "Tiger", "Deer", "Deer", "Dog", "Monkey", "Mongoose", "Monkey",
        "Lion", "Horse", "Lion", "Cow", "Elephant"]
YONI_ENEMIES = [{"Cow", "Tiger"}, {"Elephant", "Lion"}, {"Horse", "Buffalo"},
                {"Dog", "Deer"}, {"Serpent", "Mongoose"}, {"Monkey", "Sheep"},
                {"Cat", "Rat"}]

DEVA = {0, 4, 6, 7, 12, 14, 16, 21, 26}
RAKSHASA = {2, 8, 9, 13, 15, 17, 18, 22, 23}

FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"}, "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"}, "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"}, "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
}
ENEMIES = {
    "Sun": {"Venus", "Saturn"}, "Moon": set(), "Mars": {"Mercury"},
    "Mercury": {"Moon"}, "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"}, "Saturn": {"Sun", "Moon", "Mars"},
}


def rel(a, b):  # how planet a sees planet b: 2 friend, 1 neutral, 0 enemy
    if b in FRIENDS[a]:
        return 2
    if b in ENEMIES[a]:
        return 0
    return 1


def gana(n):
    return "Deva" if n in DEVA else "Rakshasa" if n in RAKSHASA else "Manushya"


def nadi(n):
    return ["Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi"][n % 6]


def guna(r1, n1, r2, n2):
    s = {}
    a, b = VARNA[r1], VARNA[r2]
    s["Varna"] = (1, 1 if abs(a - b) <= 1 else 0)

    g1, g2 = VASHYA_GROUP[r1], VASHYA_GROUP[r2]
    s["Vashya"] = (2, (VASHYA_SCORE[g1][g2] + VASHYA_SCORE[g2][g1]) / 2)

    t1 = ((n2 - n1) % 27 + 1) % 9
    t2 = ((n1 - n2) % 27 + 1) % 9
    s["Tara"] = (3, sum(1.5 for t in (t1, t2) if t not in (3, 5, 7)))

    y1, y2 = YONI[n1], YONI[n2]
    if y1 == y2:
        ys = 4
    elif {y1, y2} in YONI_ENEMIES:
        ys = 0
    else:
        ys = 2  # simplified: full 14x14 matrix can be added later
    s["Yoni"] = (4, ys)

    l1, l2 = LORDS[r1], LORDS[r2]
    if l1 == l2:
        gm = 5
    else:
        pair = tuple(sorted((rel(l1, l2), rel(l2, l1)), reverse=True))
        gm = {(2, 2): 5, (2, 1): 4, (1, 1): 3, (2, 0): 1,
              (1, 0): 0.5, (0, 0): 0}[pair]
    s["Graha Maitri"] = (5, gm)

    gs = {gana(n1), gana(n2)}
    if len(gs) == 1:
        gn = 6
    elif gs == {"Deva", "Manushya"}:
        gn = 5
    elif gs == {"Deva", "Rakshasa"}:
        gn = 1
    else:
        gn = 0
    s["Gana"] = (6, gn)

    d = (r2 - r1) % 12 + 1
    s["Bhakoot"] = (7, 0 if d in (2, 12, 5, 9, 6, 8) else 7)

    s["Nadi"] = (8, 0 if nadi(n1) == nadi(n2) else 8)
    return s


PLANETS = {"Sun": swe.SUN, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
           "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN}


def planet_signs(dt_utc):
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                    dt_utc.hour + dt_utc.minute / 60)
    return {n: int(swe.calc_ut(jd, p, swe.FLG_SIDEREAL)[0][0] // 30)
            for n, p in PLANETS.items()}


def day_planets(dob, place):
    """Planet signs at local noon, plus whether they stay in the same signs all day."""
    _, _, tz = locate(place)
    y, m, d = map(int, dob.split("-"))
    start = datetime(y, m, d, tzinfo=ZoneInfo(tz))
    pts = [planet_signs((start + timedelta(hours=h)).astimezone(timezone.utc))
           for h in (0, 12, 23.9)]
    return pts[1], pts[0] == pts[1] == pts[2]


def harmony(r1, r2):
    """0..1 friendship between the lords of two signs."""
    l1, l2 = LORDS[r1], LORDS[r2]
    if l1 == l2:
        return 1.0
    a, b = rel(l1, l2), rel(l2, l1)
    return {(2, 2): 1.0, (2, 1): 0.8, (1, 1): 0.6, (2, 0): 0.2,
            (1, 0): 0.1, (0, 0): 0.0}[(max(a, b), min(a, b))]


def extras(p1, p2):
    sun = harmony(p1["Sun"], p2["Sun"]) * 10
    trio = sum(harmony(p1[n], p2[n]) for n in ("Mercury", "Venus", "Jupiter")) / 3 * 10
    pen = 0.0
    for n in ("Mars", "Saturn"):
        d = (p2[n] - p1[n]) % 12 + 1
        pen += 2.5 if d in (6, 8) else 1.0 if d in (2, 12) else 0.0
    ex = {"Sun sign": [10, round(sun, 1)],
          "Mind, love and wisdom": [10, round(trio, 1)]}
    return ex, round(min(pen, 5.0), 1)


def compare(dob1, place1, dob2, place2):
    """Score out of 100: Guna Milan = 80, Sun sign = 10, Mercury/Venus/Jupiter = 10,
    minus up to 5 for Mars/Saturn clashes."""
    (m1, opts1) = moon_options(dob1, place1)
    (m2, opts2) = moon_options(dob2, place2)
    (p1, st1) = day_planets(dob1, place1)
    (p2, st2) = day_planets(dob2, place2)
    breakdown = guna(m1[0], m1[1], m2[0], m2[1])
    g = total_of(breakdown)
    ex, pen = extras(p1, p2)
    extra_total = sum(v[1] for v in ex.values()) - pen

    def final(gt):
        return max(0, min(100, round(gt / 36 * 80 + extra_total)))

    totals = [total_of(guna(*a, *b)) for a, b in product(opts1, opts2)]
    confident = len(opts1) == 1 and len(opts2) == 1 and st1 and st2
    return {
        "person1": (RASHIS[m1[0]], NAKSHATRAS[m1[1]]),
        "person2": (RASHIS[m2[0]], NAKSHATRAS[m2[1]]),
        "breakdown": breakdown,
        "extras": ex,
        "penalty": pen,
        "guna_36": g,
        "score_100": final(g),
        "confidence": "high" if confident else "approximate",
        "range_100": (final(min(totals)), final(max(totals))),
    }


def total_of(breakdown):
    return sum(v[1] for v in breakdown.values())


if __name__ == "__main__":
    r = compare("1998-05-14", "Hyderabad, India", "1999-11-02", "Mumbai, India")
    print(r["person1"], r["person2"])
    for k, (mx, got) in r["breakdown"].items():
        print(f"{k:13s} {got}/{mx}")
    print("Guna:", r["guna_36"], "/36 ->", r["score_100"], "/100")
    print("Confidence:", r["confidence"], "range:", r["range_100"])
