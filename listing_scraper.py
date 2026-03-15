"""
Airbnb Listing Scraper — v3
============================
Scrapes all fields needed for the P&L analyser from any Airbnb listing URL.
Handles modern Airbnb (2024/2025) which uses niobeClientData hydration
(no longer __NEXT_DATA__).

Usage (standalone):
    python listing_scraper.py https://www.airbnb.co.uk/rooms/12345

Usage (in app):
    from listing_scraper import scrape_listing
    data = scrape_listing("https://www.airbnb.co.uk/rooms/12345")
"""

import requests
import json
import re
import sys
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

# ── Browser-realistic headers ────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

# ── Amenity keyword map ───────────────────────────────────────────────────────
AMENITY_KEYWORDS = {
    "amen_hot_tub":             ["hot tub", "jacuzzi", "whirlpool"],
    "amen_pool":                ["pool", "swimming pool"],
    "amen_gym":                 ["gym", "fitness center", "fitness centre", "exercise room"],
    "amen_ev_charger":          ["ev charger", "electric vehicle charger"],
    "amen_sauna":               ["sauna"],
    "amen_fireplace":           ["fireplace", "indoor fireplace", "fire place", "wood burner"],
    "amen_dedicated_workspace": ["dedicated workspace", "dedicated work space"],
    "amen_netflix":             ["netflix", "apple tv", "amazon prime", "disney+",
                                 "smart tv", "streaming", "hbo", "sky tv", " tv "],
    "amen_wifi":                ["wifi", "wi-fi", "wireless internet"],
    "amen_free_parking":        ["free parking", "free street parking", "free driveway",
                                 "free residential parking", "free on-street parking",
                                 "parking on premises", "free parking on premises"],
    "amen_air_conditioning":    ["air conditioning", "central air", "air con", "a/c",
                                 "heating and cooling"],
    "amen_breakfast":           ["breakfast"],
    "amen_self_check-in":       ["self check-in", "self checkin", "lockbox", "keypad",
                                 "smart lock", "key locker"],
    "amen_washer":              ["washer", "washing machine", "laundry machine"],
    "amen_dryer":               ["dryer", "tumble dryer", "clothes dryer"],
    "amen_dishwasher":          ["dishwasher"],
    "amen_espresso_machine":    ["espresso machine", "nespresso", "coffee maker",
                                 "coffee machine", "coffee press"],
    "amen_piano":               ["piano"],
    "amen_baby_monitor":        ["baby monitor", "crib", "cot", "high chair"],
    "amen_elevator":            ["elevator", "lift"],
    "amen_waterfront":          ["waterfront", "water view", "river view", "riverside"],
    "amen_garden":              ["garden", "backyard", "patio", "outdoor space", "courtyard"],
    "amen_balcony":             ["balcony", "terrace", "deck"],
    "amen_harbor_view":         ["harbor view", "harbour view", "sea view", "ocean view",
                                 "lake view", "mountain view"],
}


# ── URL utilities ─────────────────────────────────────────────────────────────

def _extract_listing_id(url: str) -> str | None:
    m = re.search(r"/rooms/(\d+)", url)
    if m:
        return m.group(1)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("id", "listing_id"):
        if key in qs:
            return qs[key][0]
    return None


def _clean_url(url: str) -> str:
    listing_id = _extract_listing_id(url)
    if listing_id:
        return f"https://www.airbnb.co.uk/rooms/{listing_id}"
    parsed = urlparse(url)
    return f"https://www.airbnb.co.uk{parsed.path.rstrip('/')}"


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch_page(url: str, timeout: int = 20) -> str | None:
    """Fetch the listing page. Seeds cookies via homepage hit first."""
    session = requests.Session()
    try:
        session.get("https://www.airbnb.co.uk", headers=HEADERS, timeout=10)
        time.sleep(random.uniform(1.5, 3.0))
    except Exception:
        pass

    for attempt in range(3):
        try:
            resp = session.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (403, 429, 503):
                time.sleep((attempt + 1) * 4)
            else:
                time.sleep(2)
        except requests.RequestException:
            time.sleep(2)
    return None


# ── Data extraction ────────────────────────────────────────────────────────────

def _extract_page_data(html: str) -> dict:
    """
    Extract the main data blob from the page.
    Modern Airbnb uses niobeClientData instead of __NEXT_DATA__.
    Falls back to __NEXT_DATA__ for older versions.
    Returns the primary data dict.
    """
    soup = BeautifulSoup(html, "html.parser")

    # ── Method 1: niobeClientData (modern Airbnb 2024/2025) ──────────────────
    for script in soup.find_all("script"):
        t = script.string or ""
        if "niobeClientData" not in t or len(t) < 10000:
            continue
        try:
            blob = json.loads(t)
            niobe = blob.get("niobeClientData", [])
            if niobe and isinstance(niobe[0], list) and len(niobe[0]) > 1:
                return {"_source": "niobe", "_raw": t, "data": niobe[0][1]}
        except (json.JSONDecodeError, IndexError, KeyError):
            pass

    # ── Method 2: __NEXT_DATA__ (older Airbnb) ───────────────────────────────
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if tag and tag.string:
        try:
            return {"_source": "next_data", "_raw": tag.string,
                    "data": json.loads(tag.string)}
        except json.JSONDecodeError:
            pass

    # Regex fallback for __NEXT_DATA__
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]*?)</script>', html)
    if m:
        try:
            return {"_source": "next_data", "_raw": m.group(1),
                    "data": json.loads(m.group(1).strip())}
        except json.JSONDecodeError:
            pass

    # ── Method 3: any large script with key listing fields ───────────────────
    for script in soup.find_all("script"):
        t = script.string or ""
        if len(t) > 20000 and ("personCapacity" in t or "overviewItems" in t):
            try:
                start = t.index("{")
                return {"_source": "inline", "_raw": t,
                        "data": json.loads(t[start:])}
            except (ValueError, json.JSONDecodeError):
                pass

    return {"_source": "none", "_raw": html, "data": {}}


# ── Deep search helpers ───────────────────────────────────────────────────────

def _deep_get(obj, key: str, _seen=None):
    """Recursively find the FIRST occurrence of key."""
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return None
    _seen.add(oid)
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _deep_get(v, key, _seen)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = _deep_get(item, key, _seen)
            if r is not None:
                return r
    return None


def _deep_get_all(obj, key: str, results=None, _seen=None) -> list:
    """Collect ALL values for key anywhere in the structure."""
    if results is None:
        results = []
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return results
    _seen.add(oid)
    if isinstance(obj, dict):
        if key in obj:
            results.append(obj[key])
        for v in obj.values():
            _deep_get_all(v, key, results, _seen)
    elif isinstance(obj, list):
        for item in obj:
            _deep_get_all(item, key, results, _seen)
    return results


# ── Core parsing ──────────────────────────────────────────────────────────────

def _parse_overview_text(text: str, result: dict):
    """Parse strings like '4 guests', '2 bedrooms', '3 beds', '1 bath'."""
    text = str(text).strip().lower()
    m = re.match(r"(\d+)\s+guest", text)
    if m and "accommodates" not in result:
        result["accommodates"] = int(m.group(1))
    m = re.match(r"(\d+)\s+bedroom", text)
    if m and "bedrooms" not in result:
        result["bedrooms"] = int(m.group(1))
    if re.match(r"studio", text) and "bedrooms" not in result:
        result["bedrooms"] = 0
    m = re.match(r"(\d+)\s+bed\b", text)
    if m and "beds" not in result:
        result["beds"] = int(m.group(1))
    m = re.match(r"([\d.]+)\s+bath", text)
    if m and "bathrooms" not in result:
        result["bathrooms"] = float(m.group(1))


def _extract_from_niobe(data: dict, result: dict):
    """
    Parse Airbnb's niobeClientData[0][1] structure.
    This is a GraphQL response with a specific shape.
    """
    raw = json.dumps(data)

    # ── Listing name ──────────────────────────────────────────────────────────
    # listingTitle is the most reliable key (appears near personCapacity)
    for k in ("listingTitle", "headline"):
        v = _deep_get(data, k)
        if v and isinstance(v, str) and len(v) > 3:
            result["listing_name"] = v[:120]
            break
    if "listing_name" not in result:
        # "name" near "personCapacity" — find in the JSON by proximity
        m = re.search(r'"name"\s*:\s*"([^"]{10,100})"\s*,\s*"personCapacity"', raw)
        if m:
            result["listing_name"] = m.group(1)

    # ── Property details from overviewItems ───────────────────────────────────
    # overviewItems: [{"title": "8 guests"}, {"title": "3 bedrooms"}, ...]
    all_overview = _deep_get_all(data, "overviewItems")
    for items in all_overview:
        if isinstance(items, list):
            for item in items:
                title = item.get("title", "") if isinstance(item, dict) else str(item)
                _parse_overview_text(title, result)

    # Also try subtitleItems and detailItems for same format
    for key in ("subtitleItems", "detailItems", "highlights"):
        all_items = _deep_get_all(data, key)
        for items in all_items:
            if isinstance(items, list):
                for item in items:
                    title = item.get("title", "") if isinstance(item, dict) else str(item)
                    _parse_overview_text(title, result)

    # ── Direct capacity/room fields ───────────────────────────────────────────
    if "accommodates" not in result:
        for k in ("personCapacity", "person_capacity", "maxGuestCapacity"):
            v = _deep_get(data, k)
            if v is not None:
                try:
                    result["accommodates"] = int(float(str(v)))
                    break
                except (ValueError, TypeError):
                    pass

    # ── Room type ─────────────────────────────────────────────────────────────
    for k in ("roomType", "room_type", "room_type_category"):
        v = _deep_get(data, k)
        if v and isinstance(v, str):
            result["room_type_raw"] = v
            result["is_entire_home"] = 1 if "entire" in v.lower() else 0
            break
    # Infer from property type string
    if "is_entire_home" not in result:
        m = re.search(r'"(Entire\s+\w+|Private\s+room|Hotel\s+room|Shared\s+room)"', raw)
        if m:
            rt = m.group(1).lower()
            result["room_type_raw"] = m.group(1)
            result["is_entire_home"] = 1 if "entire" in rt else 0

    # ── Price ─────────────────────────────────────────────────────────────────
    # Try structuredDisplayPrice
    sdp = _deep_get(data, "structuredDisplayPrice")
    if isinstance(sdp, dict):
        for path in [["primaryLine", "price"], ["primaryLine", "accessibilityLabel"]]:
            obj = sdp
            for k in path:
                obj = obj.get(k) if isinstance(obj, dict) else None
            if obj:
                p = _parse_price_string(str(obj))
                if p:
                    result["nightly_price"] = p
                    break

    if "nightly_price" not in result:
        # Look for price patterns in the raw JSON
        # Match "amount": "150" or "price": 150 near "GBP"
        price_patterns = [
            r'"amount"\s*:\s*"(\d+(?:\.\d+)?)"',
            r'"price"\s*:\s*(\d+(?:\.\d+)?)\s*[,}]',
            r'"nightlyPrice"\s*:\s*"?(\d+(?:\.\d+)?)"?',
            r'[£$€](\d{2,4}(?:\.\d{2})?)\s*/\s*night',
            r'"rate"\s*:\s*"?(\d+(?:\.\d+)?)"?',
        ]
        for pattern in price_patterns:
            m = re.search(pattern, raw)
            if m:
                p = _parse_price_string(m.group(1))
                if p:
                    result["nightly_price"] = p
                    break

    # ── Host info ─────────────────────────────────────────────────────────────
    for k in ("isSuperhost", "is_superhost"):
        v = _deep_get(data, k)
        if v is not None:
            result["is_superhost"] = 1 if v in (True, "true", 1, "t") else 0
            break

    for k in ("isInstantBookable", "instantBookable", "instant_bookable"):
        v = _deep_get(data, k)
        if v is not None:
            result["instant_bookable"] = 1 if v in (True, "true", 1, "t") else 0
            break

    for k in ("responseRate", "host_response_rate"):
        v = _deep_get(data, k)
        if v is not None:
            try:
                pct = float(str(v).replace("%", "").strip())
                result["host_response_rate"] = round(pct / 100 if pct > 1 else pct, 2)
                break
            except (ValueError, TypeError):
                pass

    for k in ("responseTime", "host_response_time"):
        v = _deep_get(data, k)
        if v and isinstance(v, str):
            result["host_response_time"] = v
            break

    # ── Reviews ───────────────────────────────────────────────────────────────
    for k in ("overallRating", "starRating", "rating", "reviewScore",
              "localizedOverallRating"):
        v = _deep_get(data, k)
        if v is not None:
            try:
                s = float(v)
                if 0 < s <= 5:
                    result["review_scores_rating"] = round(s, 2)
                    break
                elif 5 < s <= 10:
                    result["review_scores_rating"] = round(s / 2, 2)
                    break
            except (ValueError, TypeError):
                pass

    for k in ("reviewCount", "reviewsCount", "totalReviews", "numberOfReviews"):
        v = _deep_get(data, k)
        if v is not None:
            try:
                result["number_of_reviews"] = int(float(str(v)))
                break
            except (ValueError, TypeError):
                pass

    # Review subscores
    subscore_map = {
        "review_scores_cleanliness":   ("cleanliness", "cleanlinessRating"),
        "review_scores_location":      ("location", "locationRating"),
        "review_scores_value":         ("value", "valueRating"),
        "review_scores_checkin":       ("checkin", "checkIn", "checkinRating"),
        "review_scores_communication": ("communication", "communicationRating"),
    }
    for field, keys in subscore_map.items():
        for k in keys:
            v = _deep_get(data, k)
            if v is not None:
                try:
                    s = float(v)
                    if 0 < s <= 5:
                        result[field] = round(s, 2)
                        break
                    elif 5 < s <= 10:
                        result[field] = round(s / 2, 2)
                        break
                except (ValueError, TypeError):
                    pass

    # ── Instant bookable / min nights (often absent when no dates) ─────────────
    for k in ("isInstantBookable", "instantBookable", "instant_bookable", "instantBook"):
        v = _deep_get(data, k)
        if v is not None:
            result["instant_bookable"] = 1 if v in (True, "true", 1, "t") else 0
            break

    for k in ("minNights", "minimum_nights", "minStay", "minimumNights",
              "minNightsDFW", "minNightsDisplay", "minNightsLong"):
        v = _deep_get(data, k)
        if v is not None:
            try:
                result["minimum_nights"] = int(float(str(v)))
                break
            except (ValueError, TypeError):
                pass

    # ── Amenities ─────────────────────────────────────────────────────────────
    amen_titles = []

    # Method A: previewAmenitiesGroups (most reliable in 2024/2025 niobe format)
    # Structure: previewAmenitiesGroups -> list of groups -> each has "amenities" list
    groups_found = _deep_get_all(data, "previewAmenitiesGroups")
    for group_list in groups_found:
        if isinstance(group_list, list):
            for group in group_list:
                if isinstance(group, dict):
                    for amenity in group.get("amenities", []):
                        if isinstance(amenity, dict):
                            avail = amenity.get("available", True)
                            t = amenity.get("title", "")
                            if t and avail is not False:
                                amen_titles.append(str(t))

    # Method B: seeAllAmenitiesGroups (full amenity list, shown in modal)
    all_groups = _deep_get_all(data, "seeAllAmenitiesGroups")
    for group_list in all_groups:
        if isinstance(group_list, list):
            for group in group_list:
                if isinstance(group, dict):
                    for amenity in group.get("amenities", []):
                        if isinstance(amenity, dict):
                            avail = amenity.get("available", True)
                            t = amenity.get("title", "")
                            if t and avail is not False:
                                amen_titles.append(str(t))

    # Method C: flat amenities/allAmenities lists
    for k in ("allAmenities", "amenities", "amenityGroups"):
        all_vals = _deep_get_all(data, k)
        for v in all_vals:
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        t = item.get("title", "") or item.get("name", "")
                        avail = item.get("available", True)
                        if t and avail is not False:
                            amen_titles.append(str(t))

    # Method D: AMENITIES_DEFAULT section in raw JSON (legacy fallback)
    if len(amen_titles) < 3:
        skip_titles = {"what this place offers", "bedroom and laundry", "bathroom",
                       "kitchen and dining", "heating and cooling", "internet and office",
                       "parking and facilities", "outdoor", "safety items", "not included",
                       "things to know", "house rules", "location", "reviews", "read more",
                       "show more", "superhost", "unbeatable location"}
        for amen_start in [m.start() for m in re.finditer(r'"AMENITIES_DEFAULT"', raw)]:
            chunk = raw[amen_start: amen_start + 8000]
            for t in re.findall(r'"title"\s*:\s*"([^"]+)"', chunk):
                if len(t) > 2 and t.lower() not in skip_titles:
                    amen_titles.append(t)

    result["_amenity_titles"] = amen_titles

    # ── Location ──────────────────────────────────────────────────────────────
    for k in ("localizedLocation", "city", "neighbourhood", "publicAddress",
              "localized_city", "neighborhood_overview"):
        v = _deep_get(data, k)
        if v and isinstance(v, str) and len(v) > 1:
            result["location_hint"] = v[:100]
            break


def _parse_price_string(text: str) -> float | None:
    """Extract a sensible nightly price (£10–£3000) from any string."""
    if not text:
        return None
    clean = re.sub(r"[£$€,\s]", "", str(text))
    numbers = re.findall(r"\d+(?:\.\d+)?", clean)
    for n in numbers:
        try:
            val = float(n)
            if 10 <= val <= 3000:
                return round(val, 2)
        except ValueError:
            pass
    return None


def _html_fallback(html: str, result: dict):
    """Last-resort HTML parsing for any still-missing fields."""
    soup = BeautifulSoup(html, "html.parser")

    # Title tag → listing name
    if "listing_name" not in result:
        title = soup.find("title")
        if title:
            name = re.sub(r"\s*[-|]\s*Airbnb.*$", "", title.get_text(strip=True), flags=re.IGNORECASE)
            if name and len(name) > 5:
                result["listing_name"] = name[:120]

    # Page visible text → overview items
    page_text = soup.get_text(" ", strip=True)
    for chunk in re.findall(r"[\d.]+\s+(?:guest|bedroom|bed\b|bath|studio)[s]?", page_text, re.IGNORECASE):
        _parse_overview_text(chunk, result)

    # Price from visible text — try multiple patterns in order of reliability
    if "nightly_price" not in result:
        # Best: "£XX / night" or "£XX per night"
        hits = re.findall(r"[£$€]\s*(\d{2,4}(?:\.\d{2})?)\s*(?:/\s*night|per\s*night)",
                          page_text, re.IGNORECASE)
        if not hits:
            # Fallback: any £XXX amount on the page
            hits = re.findall(r"[£$€]\s*(\d{2,4}(?:\.\d{2})?)", page_text)
        for h in hits:
            p = _parse_price_string(h)
            if p:
                result["nightly_price"] = p
                break

    # Instant bookable from page text
    if "instant_bookable" not in result:
        pl = page_text.lower()
        if "instant book" in pl or "book instantly" in pl:
            result["instant_bookable"] = 1
        elif "request to book" in pl:
            result["instant_bookable"] = 0

    # Minimum nights from page text
    if "minimum_nights" not in result:
        m = re.search(r"(\d+)\s*(?:-\s*)?night\s+minimum", page_text, re.IGNORECASE)
        if not m:
            m = re.search(r"minimum\s+(?:stay|nights?)[:\s]+(\d+)", page_text, re.IGNORECASE)
        if m:
            try:
                result["minimum_nights"] = int(m.group(1))
            except (ValueError, TypeError):
                pass

    # Amenities from page text (last resort)
    if not result.get("_amenity_titles"):
        result["_amenity_titles"] = []
    if len(result["_amenity_titles"]) < 3:
        page_lower = page_text.lower()
        for key, keywords in AMENITY_KEYWORDS.items():
            if result.get(key, 0) == 0:
                if any(kw in page_lower for kw in keywords):
                    result[key] = 1


def _match_amenities(result: dict):
    """Match collected amenity titles against AMENITY_KEYWORDS."""
    titles = result.pop("_amenity_titles", [])
    if not titles:
        return
    joined = " | ".join(str(t).lower() for t in titles)
    for key, keywords in AMENITY_KEYWORDS.items():
        if result.get(key, 0) == 0:
            result[key] = 1 if any(kw in joined for kw in keywords) else 0


# ── Neighbourhood inference ───────────────────────────────────────────────────

NEIGHBOURHOOD_HINTS = {
    # Bristol
    "clifton": "Clifton", "harbourside": "Harbourside", "harbour": "Harbourside",
    "bedminster": "Bedminster", "southville": "Southville", "cotham": "Cotham",
    "redland": "Redland", "easton": "Easton", "stokes croft": "Stokes Croft",
    "montpelier": "Montpelier", "totterdown": "Totterdown", "bishopston": "Bishopston",
    "horfield": "Horfield", "henleaze": "Henleaze", "fishponds": "Fishponds",
    "brislington": "Brislington", "knowle": "Knowle", "hotwells": "Hotwells",
    "st pauls": "St Pauls", "st werburghs": "St Werburghs",
    # Edinburgh
    "old town": "Old Town, Princes Street and Leith Street",
    "new town": "New Town West", "leith": "Leith Walk",
    "morningside": "Morningside", "stockbridge": "Stockbridge",
    "bruntsfield": "Bruntsfield", "newington": "Newington",
    "marchmont": "Marchmont", "tollcross": "Tollcross",
    # London
    "shoreditch": "Shoreditch", "brixton": "Brixton", "hackney": "Hackney",
    "camden": "Camden Town", "islington": "Islington", "chelsea": "Chelsea",
    "kensington": "Kensington", "notting hill": "Notting Hill",
    "peckham": "Peckham", "dalston": "Dalston", "bethnal green": "Bethnal Green",
    # Manchester
    "northern quarter": "Northern Quarter", "ancoats": "Ancoats",
    "didsbury": "Didsbury", "chorlton": "Chorlton", "salford": "Salford",
}


def _infer_neighbourhood(result: dict) -> str:
    hint = " ".join([
        result.get("location_hint", ""),
        result.get("listing_name", ""),
    ]).lower()
    for keyword, neighbourhood in NEIGHBOURHOOD_HINTS.items():
        if keyword in hint:
            return neighbourhood
    return ""


def _room_type_to_property_type(raw: str) -> str:
    r = raw.lower() if raw else ""
    if "entire" in r:
        return "Entire home"
    if "private" in r:
        return "Private room in home"
    if "shared" in r:
        return "Shared room"
    if "hotel" in r:
        return "Hotel room"
    return "Entire home"


def _normalise_response_time(raw: str) -> str:
    r = raw.lower() if raw else ""
    if "hour" in r and "few" not in r:
        return "within an hour"
    if "few hours" in r or ("hour" in r and "few" in r):
        return "within a few hours"
    if "day" in r and "few" not in r:
        return "within a day"
    if "few days" in r or ("day" in r and "few" in r):
        return "a few days or more"
    return "within a few hours"


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_listing(url: str, verbose: bool = True) -> dict:
    """
    Scrape an Airbnb listing URL. Returns a complete PROPERTY-compatible dict.
    """
    if verbose:
        print(f"Scraping: {url}")

    clean = _clean_url(url)
    html = _fetch_page(clean)

    if not html:
        return {
            "scrape_status": "FAILED — could not fetch page. Check the URL or try again.",
            "listing_url": clean,
        }

    if verbose:
        print("  Page fetched. Extracting data...")

    page_data = _extract_page_data(html)
    source    = page_data["_source"]
    data      = page_data["data"]

    if verbose:
        print(f"  Data source: {source}")

    result = {}

    if source in ("niobe", "next_data", "inline") and data:
        _extract_from_niobe(data, result)

    # HTML fallback for anything still missing
    _html_fallback(html, result)

    # Match amenity titles → amenity flags
    _match_amenities(result)

    # ── Build the complete PROPERTY dict ──────────────────────────────────────
    beds_default = max(result.get("bedrooms", 1), 1)
    rating = result.get("review_scores_rating", 4.5)

    output = {
        # Property details
        "neighbourhood":               _infer_neighbourhood(result) or "Central",
        "property_type":               _room_type_to_property_type(result.get("room_type_raw", "")),
        "is_entire_home":              result.get("is_entire_home", 1),
        "bedrooms":                    result.get("bedrooms", 1),
        "beds":                        result.get("beds", beds_default),
        "bathrooms":                   result.get("bathrooms", 1.0),
        "accommodates":                result.get("accommodates", 2),
        # Pricing
        "nightly_price":               result.get("nightly_price", 80),
        "minimum_nights":              result.get("minimum_nights", 2),
        "days_available_year":         200,  # not on listing page
        # Host
        "is_superhost":                result.get("is_superhost", 0),
        "instant_bookable":            result.get("instant_bookable", 0),
        "host_response_time":          _normalise_response_time(result.get("host_response_time", "")),
        "host_response_rate":          result.get("host_response_rate", 0.90),
        "host_acceptance_rate":        0.85,
        "host_years_experience":       1.0,
        "host_listings_count":         1,
        # Reviews
        "review_scores_rating":        result.get("review_scores_rating", 4.5),
        "review_scores_cleanliness":   result.get("review_scores_cleanliness", rating),
        "review_scores_checkin":       result.get("review_scores_checkin", rating),
        "review_scores_communication": result.get("review_scores_communication", rating),
        "review_scores_location":      result.get("review_scores_location", rating),
        "review_scores_value":         result.get("review_scores_value", min(rating, 4.5)),
        "number_of_reviews":           result.get("number_of_reviews", 0),
        "reviews_per_month":           2.0,
        # Amenities
        "amen_hot_tub":                result.get("amen_hot_tub", 0),
        "amen_pool":                   result.get("amen_pool", 0),
        "amen_gym":                    result.get("amen_gym", 0),
        "amen_ev_charger":             result.get("amen_ev_charger", 0),
        "amen_sauna":                  result.get("amen_sauna", 0),
        "amen_fireplace":              result.get("amen_fireplace", 0),
        "amen_dedicated_workspace":    result.get("amen_dedicated_workspace", 0),
        "amen_netflix":                result.get("amen_netflix", 0),
        "amen_wifi":                   result.get("amen_wifi", 0),
        "amen_free_parking":           result.get("amen_free_parking", 0),
        "amen_air_conditioning":       result.get("amen_air_conditioning", 0),
        "amen_breakfast":              result.get("amen_breakfast", 0),
        "amen_self_check-in":          result.get("amen_self_check-in", 0),
        "amen_washer":                 result.get("amen_washer", 0),
        "amen_dryer":                  result.get("amen_dryer", 0),
        "amen_dishwasher":             result.get("amen_dishwasher", 0),
        "amen_espresso_machine":       result.get("amen_espresso_machine", 0),
        "amen_piano":                  result.get("amen_piano", 0),
        "amen_baby_monitor":           result.get("amen_baby_monitor", 0),
        "amen_elevator":               result.get("amen_elevator", 0),
        "amen_waterfront":             result.get("amen_waterfront", 0),
        "amen_garden":                 result.get("amen_garden", 0),
        "amen_balcony":                result.get("amen_balcony", 0),
        "amen_harbor_view":            result.get("amen_harbor_view", 0),
        # Costs — user must fill in
        "monthly_mortgage_or_rent":    0,
        "monthly_bills":               0,
        "monthly_insurance":           0,
        "cleaning_cost_per_stay":      0,
        "consumables_per_stay":        0,
        "annual_maintenance":          0,
        "initial_setup_cost":          0,
        "avg_stay_length_nights":      3,
        # Metadata
        "listing_name":                result.get("listing_name", ""),
        "listing_url":                 clean,
        "scrape_status":               "pending",
    }
    output["scrape_status"] = _build_status(result, output)

    if verbose:
        _print_summary(output)

    return output


def _build_status(raw: dict, output: dict) -> str:
    key_fields = ["nightly_price", "bedrooms", "review_scores_rating",
                  "is_superhost", "instant_bookable", "accommodates"]
    found_key = sum(1 for k in key_fields if k in raw)
    scraped = sum(
        1 for k in ("nightly_price", "bedrooms", "beds", "bathrooms",
                    "accommodates", "is_superhost", "instant_bookable",
                    "review_scores_rating", "number_of_reviews", "minimum_nights")
        if k in raw
    )
    amenity_count = sum(output.get(k, 0) for k in AMENITY_KEYWORDS)
    if found_key >= 4:
        return f"OK — {scraped} core fields + {amenity_count}/24 amenities scraped"
    elif found_key >= 2:
        return f"PARTIAL — {scraped} core fields + {amenity_count}/24 amenities (some gaps)"
    elif found_key >= 1:
        return "MINIMAL — Airbnb may have partially blocked scraping; review & fill fields"
    else:
        return "BLOCKED — Airbnb blocked the request; fill all fields manually"


def _print_summary(output: dict):
    amenity_count = sum(output.get(k, 0) for k in AMENITY_KEYWORDS)
    amenity_names = [k.replace("amen_", "").replace("_", " ").replace("-", " ")
                     for k in AMENITY_KEYWORDS if output.get(k, 0) == 1]
    print(f"\n  ✅  Scrape complete")
    print(f"     Name:         {output['listing_name'][:70] or '—'}")
    print(f"     Price:        £{output['nightly_price']}/night")
    print(f"     Capacity:     {output['accommodates']} guests · "
          f"{output['bedrooms']} bed · "
          f"{output['bathrooms']} bath")
    print(f"     Type:         {output['property_type']}")
    print(f"     Superhost:    {'Yes' if output['is_superhost'] else 'No'}")
    print(f"     Instant book: {'Yes' if output['instant_bookable'] else 'No'}")
    print(f"     Rating:       {output['review_scores_rating']} ★  "
          f"({output['number_of_reviews']} reviews)")
    print(f"     Min nights:   {output['minimum_nights']}")
    print(f"     Amenities:    {amenity_count}/24 — {', '.join(amenity_names[:8]) or 'none detected'}")
    print(f"     Status:       {output['scrape_status']}")
    print(f"\n  ⚠️  Fill in: costs (mortgage/bills/insurance etc.), "
          f"days_available_year, neighbourhood if wrong")


# ── Notebook helper ───────────────────────────────────────────────────────────

def scrape_to_notebook(url: str) -> dict:
    """
    Auto-populate the notebook PROPERTY dict from a listing URL.

    Example:
        from listing_scraper import scrape_to_notebook
        PROPERTY = scrape_to_notebook("https://www.airbnb.co.uk/rooms/12345")
    """
    data = scrape_listing(url)
    cost_keys = {
        "monthly_mortgage_or_rent", "monthly_bills", "monthly_insurance",
        "cleaning_cost_per_stay", "consumables_per_stay",
        "annual_maintenance", "initial_setup_cost",
        "avg_stay_length_nights", "days_available_year",
        "host_years_experience", "host_listings_count",
        "host_acceptance_rate", "reviews_per_month",
    }
    meta_keys = {"listing_name", "listing_url", "scrape_status"}
    print("\n--- Copy PROPERTY dict into Cell 6.1 and fill in the cost fields ---\n")
    print("PROPERTY = {")
    for k, v in data.items():
        if k in meta_keys:
            continue
        comment = "  # ← fill in" if k in cost_keys else ""
        if isinstance(v, str):
            print(f"    '{k}': '{v}',{comment}")
        else:
            print(f"    '{k}': {v},{comment}")
    print("}")
    return data


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python listing_scraper.py <airbnb_url>")
        sys.exit(1)
    result = scrape_listing(sys.argv[1], verbose=True)
    print("\n\nFull scraped result:")
    print(json.dumps(
        {k: v for k, v in result.items() if not k.startswith("listing_url")},
        indent=2
    ))
