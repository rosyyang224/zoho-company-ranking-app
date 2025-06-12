from typing import Optional, Tuple, List
from bs4 import BeautifulSoup
import logging
import re

try:
    import us
    US_AVAILABLE = True
    US_STATES = {s.name: s.abbr for s in us.states.STATES}
    US_ABBRS = {s.abbr: s.name for s in us.states.STATES}
except ImportError:
    US_AVAILABLE = False
    US_STATES = {}
    US_ABBRS = {}

try:
    import pycountry
    PYCOUNTRY_AVAILABLE = True
    COUNTRY_NAMES = [c.name for c in pycountry.countries]
    COUNTRY_REGEX = re.compile(r"\b(" + "|".join(re.escape(name) for name in COUNTRY_NAMES) + r")\b", flags=re.IGNORECASE)
except ImportError:
    PYCOUNTRY_AVAILABLE = False

try:
    from geotext import GeoText
    GEOTEXT_AVAILABLE = True
except ImportError:
    GEOTEXT_AVAILABLE = False

try:
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="company-locator")
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False


logger = logging.getLogger(__name__)

def is_probably_junk(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    if len(text) < 6:
        return True
    if any(token in text for token in ['{', '}', '/*', '*/', '$(', 'function(', 'return', '=>']):
        return True
    if re.match(r'^[^\w\s]+$', text):  # line is mostly symbols
        return True
    return False


def extract_location_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    # known city-to-country/state map
    city_country_map = {
        "gliwice": ("Poland", None),
        "düsseldorf": ("Germany", None),
        "bc": ("Canada", "British Columbia"),
    }

    text_lower = text.lower()
    for city, (country, state) in city_country_map.items():
        if re.search(rf"\b{re.escape(city)}\b", text_lower):
            return country, state

    # US state matching
    if US_AVAILABLE:
        for state in us.states.STATES:
            # Match full state name
            if re.search(rf'\b{re.escape(state.name)}\b', text):
                print(f"[MATCH] Regex full name match: {state.name}")
                return "United States", state.name

            # Match abbreviation only if followed by zip or comma
            if re.search(rf'\b{state.abbr}\b(?=\s+\d{{5}}|\s*,)', text):
                print(f"[MATCH] Regex abbreviation + context match: {state.abbr} ({state.name})")
                return "United States", state.name
    
    # GeoText for country/city detection
    if GEOTEXT_AVAILABLE:
        try:
            places = GeoText(text)
            if places.countries:
                country = places.countries[0]
                if PYCOUNTRY_AVAILABLE:
                    try:
                        match = pycountry.countries.get(name=country) or pycountry.countries.search_fuzzy(country)[0]
                        country = match.name
                    except LookupError:
                        pass
                return country, None
        except Exception as e:
            logger.warning(f"GeoText failed: {e}")

    # Fallback: use pycountry subdivisions for postal or city-like tokens
    if PYCOUNTRY_AVAILABLE:
        tokens = re.findall(r'\b[\w\-\d]{3,}\b', text)
        for token in tokens:
            try:
                for subdiv in pycountry.subdivisions:
                    if token.lower() in subdiv.name.lower():
                        country = pycountry.countries.get(alpha_2=subdiv.country_code)
                        if country:
                            return country.name, None
            except Exception:
                continue
    
    # Fallback: Use geopy/Nominatim to geocode any city or postal-like line
    if GEOPY_AVAILABLE:
        try:
            location = geolocator.geocode(text, addressdetails=True, language='en', timeout=5)
            if location and 'country' in location.raw['address']:
                country = location.raw['address']['country']
                state = location.raw['address'].get('state')
                return country, state
        except Exception as e:
            logger.warning(f"Geopy fallback failed: {e}")

    return None, None
  
def score_location(line: str) -> int:
    line_lower = line.lower()
    score = 0

    if is_probably_junk(line):
        return -10

    # Strong signals
    if any(keyword in line_lower for keyword in ['address', 'headquartered', 'location', 'located']):
        score += 40
    if re.search(r"\d{5}(?:-\d{4})?", line):  # US ZIP code
        score += 25
    if re.search(r"[A-Z]\d[A-Z] ?\d[A-Z]\d", line, re.IGNORECASE):  # Canadian postal code
        score += 25
    if re.search(r"\d{1,4} .{2,30}(?:st|street|ave|avenue|road|rd|blvd|boulevard|lane|ln)\\b", line_lower):
        score += 25  # street-like patterns

    # Compound matches (City + Province/State + ZIP/postal)
    if re.search(r"\\b[a-zA-Z]+,\\s*[A-Z]{2,3}(?:\\s+\\d{5}|\\s+[A-Z]\\d[A-Z] ?\\d[A-Z]\\d)?", line):
        score += 30
    if re.search(r"[A-Za-z\\s]+,\\s?[A-Z]{2}\\s+\\S{3,}", line):
        score += 25  # Canada-style city + province + postal

    # Contextual: US states
    if any(state.lower() in line_lower for state in US_STATES):
        score += 20

    # ✅ Contextual: pycountry-backed match with filtering
    if PYCOUNTRY_AVAILABLE:
        tokens = re.findall(r"\\b[A-Z][a-z]+\\b", line)  # Capitalized words
        for token in tokens:
            try:
                country = pycountry.countries.search_fuzzy(token)[0]
                if country.name.lower() not in {'georgia', 'guinea'}:  # filter ambiguous
                    score += 20
                    break
            except LookupError:
                continue

    # Reduce if only vague footer content
    if any(term in line_lower for term in ['copyright', 'terms of use', 'privacy policy']):
        score -= 30
    if re.match(r'^contact us$', line_lower.strip()):
        score -= 15

    # Mild penalty if line is suspiciously short
    if len(line.strip()) < 15:
        score -= 10

    return score


def parse_contact_page(soup: BeautifulSoup, html_content: str, body_lines: List[str]) -> Tuple[Optional[str], Optional[str]]:

    candidates = []

    # Strategy 1: Contact page candidates
    for selector in [
        '[class*="address"]', '[class*="contact"]', '[class*="location"]',
        '[class*="headquarters"]', '[class*="office"]', '[id*="address"]',
        '[id*="contact"]', '[id*="location"]'
    ]:
        for element in soup.select(selector):
            if element.name == "script":
                continue
            text = element.get_text(" ", strip=True)
            if is_probably_junk(text):
                continue
            score = score_location(text)
            if score > 0:
                print(f"    [DEBUG] {selector} snippet: {text[:100]}... (score={score})")
                c, s = extract_location_from_text(text)
                candidates.append((score + 10, c, s))  # bonus for being a structured tag

    # Strategy 2: Footer
    footer = soup.find("footer")
    if footer:
        text = footer.get_text(" ", strip=True)
        if is_probably_junk(text) is False:
            score = score_location(text)
            print(f"    [DEBUG] Footer snippet: {text[:100]}... (score={score})")
            c, s = extract_location_from_text(text)
            candidates.append((score + 5, c, s))  # lower bonus than structured contact tags

    # Strategy 3: Heuristic line scan
    for line in body_lines:
        if is_probably_junk(line):
            continue
        score = score_location(line)
        if score > 0:
            print(f"    [DEBUG] Heuristic line: {line[:100]}... (score={score})")
            c, s = extract_location_from_text(line)
            candidates.append((score, c, s))

    found_countries = set()
    for line in body_lines:
        matches = COUNTRY_REGEX.findall(line)
        found_countries.update(match.strip().title() for match in matches)

    # Optional: remove near-duplicates like "United States of America" vs "United States"
    normalized_countries = {pycountry.countries.get(name=country).alpha_2 for country in found_countries if pycountry.countries.get(name=country)}

    if len(normalized_countries) >= 3:
        print(f"🌍 Multinational detected from countries: {found_countries}")
        country = "Multinational"
        state = None
        return country, state

    # Pick best-scoring valid result
    candidates = [item for item in candidates if item[1]]  # must have a country
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        top = candidates[0]
        print(f"    [DEBUG] Selected → country={top[1]}, state={top[2]} (score={top[0]})")
        return top[1], top[2]

    print("    [DEBUG] No valid candidates found.")
    return None, None


def assign_region(country: Optional[str], state: Optional[str]) -> str:
    """Map (country, state) to one of: 'NA Northeast', 'NA Midwest', 'NA South', 'NA West', 'EU', 'APAC', or 'Other'."""
    if not country:
        return "Other"
    
    if country == "Multinational":
        return "Multinational"

    if country.lower() == "united states":
        us_ne = {
            "Connecticut", "Maine", "Massachusetts", "New Hampshire",
            "Rhode Island", "Vermont", "New Jersey", "New York", "Pennsylvania"
        }
        us_mw = {
            "Illinois", "Indiana", "Michigan", "Ohio", "Wisconsin",
            "Iowa", "Kansas", "Minnesota", "Missouri", "Nebraska",
            "North Dakota", "South Dakota"
        }
        us_s = {
            "Delaware", "Florida", "Georgia", "Maryland", "North Carolina",
            "South Carolina", "Virginia", "District of Columbia", "West Virginia",
            "Alabama", "Kentucky", "Mississippi", "Tennessee",
            "Arkansas", "Louisiana", "Oklahoma", "Texas"
        }
        us_w = {
            "Arizona", "Colorado", "Idaho", "Montana", "Nevada",
            "New Mexico", "Utah", "Wyoming",
            "Alaska", "California", "Hawaii", "Oregon", "Washington"
        }

        s = (state or "").title().strip()
        if s in us_ne:
            return "NA Northeast"
        if s in us_mw:
            return "NA Midwest"
        if s in us_s:
            return "NA South"
        if s in us_w:
            return "NA West"
        return "Other"

    eu_countries = {
        'germany', 'france', 'italy', 'spain', 'netherlands', 'belgium', 
        'austria', 'switzerland', 'sweden', 'denmark', 'norway', 'finland',
        'poland', 'united kingdom', 'ireland', 'portugal', 'greece', 'czech republic'
    }

    if country.lower() in eu_countries:
        return "EU"

    apac_countries = {
        'japan', 'china', 'south korea', 'singapore', 'australia', 'india',
        'taiwan', 'hong kong', 'thailand', 'malaysia', 'philippines', 'indonesia'
    }

    if country.lower() in apac_countries:
        return "APAC"

    if country.lower() == 'canada':
        return "Other"

    return "Other"
