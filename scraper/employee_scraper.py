import re
import time
from collections import Counter
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from logging_config import logger


class MultiSourceEmployeeScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        })

    def query_wikidata_employees(self, company_name: str) -> int | None:
        """
        Query Wikidata for employee count (P1128 / P1120).
        """
        try:
            sparql_endpoint = "https://query.wikidata.org/sparql"
            query = f"""
            SELECT ?item ?itemLabel WHERE {{
              ?item rdfs:label "{company_name}"@en .
              ?item wdt:P31 ?instance .
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
            }}
            LIMIT 1
            """
            headers = {"Accept": "application/sparql-results+json"}
            r = self.session.get(sparql_endpoint, params={"query": query}, headers=headers, timeout=10)

            data = r.json()
            if not data.get("results", {}).get("bindings"):
                logger.info(f"[Wikidata] No Q‐item found for '{company_name}'.")
                return None

            qid = data["results"]["bindings"][0]["item"]["value"].split("/")[-1]
            detail_url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
            r2 = self.session.get(detail_url, timeout=10)
            jd = r2.json()

            if qid not in jd.get("entities", {}):
                logger.info(f"[Wikidata] Entity data for QID={qid} missing.")
                return None

            statements = jd["entities"][qid].get("claims", {})
            for prop in ("P1128", "P1120"):  # P1128 = number of employees, P1120 = staff
                if prop in statements:
                    for claim in statements[prop]:
                        mainsnak = claim.get("mainsnak", {})
                        if mainsnak.get("datatype") == "quantity" and "datavalue" in mainsnak:
                            valobj = mainsnak["datavalue"]["value"]
                            amount = valobj.get("amount")
                            if amount:
                                try:
                                    count = int(float(amount.replace("+", "")))
                                    logger.info(f"[Wikidata] Found {count} employees for '{company_name}'.")
                                    return count
                                except Exception:
                                    logger.info(
                                        f"[Wikidata] Unable to parse quantity '{amount}' for '{company_name}'."
                                    )
            logger.info(f"[Wikidata] No P1128/P1120 statement for '{company_name}'.")
            return None

        except Exception as e:
            logger.warning(f"[Wikidata] Exception while querying '{company_name}': {e}")
            return None

    def parse_wikipedia_infobox_employees(self, company_name: str) -> int | None:
        """
        Scrape Wiki infobox for “Employees” row.
        """
        try:
            slug = company_name.strip().replace(" ", "_")
            url = f"https://en.wikipedia.org/wiki/{slug}"
            r = self.session.get(url, timeout=10)

            if r.status_code == 404:
                logger.info(f"[Wikipedia] Page not found: {url}")
                return None
            if r.status_code != 200:
                logger.info(f"[Wikipedia] Unexpected status {r.status_code} for '{url}'")
                return None

            soup = BeautifulSoup(r.text, "html.parser")
            infobox = soup.find("table", {"class": "infobox"})
            if not infobox:
                logger.info(f"[Wikipedia] No infobox found for '{slug}'.")
                return None

            for row in infobox.find_all("tr"):
                header = row.find("th")
                if header and "employees" in header.get_text(strip=True).lower():
                    valcell = row.find("td")
                    if not valcell:
                        logger.info(f"[Wikipedia] 'Employees' header found but no <td> for '{company_name}'.")
                        return None
                    text = valcell.get_text(" ", strip=True)
                    m = re.search(r"(\d[\d,\.]*)", text)
                    if m:
                        num = m.group(1).replace(",", "").replace(".", "")
                        try:
                            count = int(num)
                            logger.info(f"[Wikipedia] Found {count} employees in infobox for '{company_name}'.")
                            return count
                        except ValueError:
                            logger.info(f"[Wikipedia] Could not parse number '{m.group(1)}'.")
                            return None
            logger.info(f"[Wikipedia] No 'Employees' row in infobox for '{company_name}'.")
            return None

        except Exception as e:
            logger.warning(f"[Wikipedia] Exception while scraping '{company_name}': {e}")
            return None

    def fetch_html_with_fallback(self, url: str) -> tuple[str | None, BeautifulSoup]:
        """
        Simple fetch with static requests; logs warnings on failure.
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return response.text, soup
        except requests.exceptions.HTTPError as http_err:
            logger.warning(f"[FetchHTML] HTTP error for URL {url}: {http_err}")
            return None, BeautifulSoup("", "html.parser")
        except Exception as e:
            logger.warning(f"[FetchHTML] General error fetching {url}: {e}")
            return None, BeautifulSoup("", "html.parser")

    def find_verified_domain(self, company_name: str) -> str | None:
        """
        Run a Bing query like “company_name official website”, pick the first non‐social/non-wiki domain.
        """
        try:
            query = f"{company_name} official website"
            search_url = "https://www.bing.com/search"
            params = {"q": query}
            r = self.session.get(search_url, params=params, timeout=10)

            if r.status_code != 200:
                logger.info(f"[DomainSearch] Bing returned status {r.status_code} for '{company_name}'.")
                return None

            soup = BeautifulSoup(r.text, "html.parser")
            for result in soup.select("li.b_algo h2 a"):
                href = result.get("href", "")
                if href.startswith("http"):
                    domain = urlparse(href).netloc.lower()
                    if any(block in domain for block in ["wikipedia.", "linkedin.", "facebook.", "twitter."]):
                        logger.debug(f"[DomainSearch] Skipping domain '{domain}'.")
                        continue
                    logger.info(f"[DomainSearch] Using domain '{domain}' for '{company_name}'.")
                    return domain
            logger.info(f"[DomainSearch] No suitable domain found for '{company_name}'.")
            return None

        except Exception as e:
            logger.warning(f"[DomainSearch] Exception for '{company_name}': {e}")
            return None

    def find_contact_link(self, soup: BeautifulSoup, base_url: str) -> str | None:
        """
        Look for any <a> that hints at 'about', 'contact', 'team', 'company'.
        """
        contact_keywords = ['about', 'contact', 'company', 'team']
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            text = a.get_text().lower()
            if any(keyword in href or keyword in text for keyword in contact_keywords):
                full_url = urljoin(base_url, a["href"])
                logger.info(f"[find_contact_link] Found potential contact/team link: {full_url}")
                return full_url
        logger.info(f"[find_contact_link] No contact/about/team link found on {base_url}")
        return None

    def extract_team_count(self, team_page_url: str) -> int | None:
        """
        Count team members by looking for selectors like '.team-member' or fallback to profile images.
        """
        try:
            html, soup = self.fetch_html_with_fallback(team_page_url)
            if not soup or not html:
                logger.info(f"[extract_team_count] Could not fetch '{team_page_url}'.")
                return None

            selectors = [
                ".team-member", ".team__person", ".staff-card", ".bio-entry",
                ".employee", ".person", ".profile", ".member"
            ]
            for selector in selectors:
                members = soup.select(selector)
                if len(members) > 1:
                    logger.info(
                        f"[extract_team_count] Found {len(members)} elements with selector '{selector}'."
                    )
                    return len(members)

            img_selectors = [
                "img.staff-photo", "img.team-photo", "img.profile-pic",
                "img.avatar", "img[alt*='team']", "img[alt*='staff']"
            ]
            for selector in img_selectors:
                pics = soup.select(selector)
                if len(pics) > 1:
                    logger.info(
                        f"[extract_team_count] Found {len(pics)} images with selector '{selector}'."
                    )
                    return len(pics)

            logger.info(f"[extract_team_count] No team‐member selectors matched >1 on '{team_page_url}'.")
            return None

        except Exception as e:
            logger.warning(f"[extract_team_count] Exception for '{team_page_url}': {e}")
            return None

    def extract_from_about_or_contact(self, soup: BeautifulSoup) -> int | None:
        """
        Look for lines like 'Employees: 500' or 'team of 200'.
        """
        try:
            text = soup.get_text(" ", strip=True)
            patterns = [
                r"employees?\s*[:\-]\s*(\d[\d,]*)",
                r"headcount\s*[:\-]\s*(\d[\d,]*)",
                r"staff\s*[:\-]\s*(\d[\d,]*)",
                r"team\s*of\s*(\d[\d,]*)",
                r"(\d[\d,]*)\s*employees?",
                r"(\d[\d,]*)\s*staff\s*members?"
            ]
            for pattern in patterns:
                for match in re.findall(pattern, text, re.IGNORECASE):
                    try:
                        count = int(match.replace(",", ""))
                        logger.info(f"[extract_from_about_or_contact] Found {count} via pattern '{pattern}'.")
                        return count
                    except ValueError:
                        continue
            logger.info(f"[extract_from_about_or_contact] No pattern matched for employees/staff.")
            return None

        except Exception as e:
            logger.warning(f"[extract_from_about_or_contact] Exception: {e}")
            return None

    def extract_from_address_tag(self, soup: BeautifulSoup) -> int | None:
        """
        Look for “(X employees)” in any <address> tag.
        """
        try:
            for addr in soup.find_all("address"):
                txt = addr.get_text(" ", strip=True)
                m = re.search(r"\((\d[\d,]*)\s+employees?\)", txt, re.IGNORECASE)
                if m:
                    count = int(m.group(1).replace(",", ""))
                    logger.info(
                        f"[extract_from_address_tag] Found '{m.group(0)}' → {count} employees."
                    )
                    return count
                else:
                    logger.debug(f"[extract_from_address_tag] Address text did not match: '{txt[:60]}...'")
            logger.info(f"[extract_from_address_tag] No '(X employees)' in any <address>.")
            return None

        except Exception as e:
            logger.warning(f"[extract_from_address_tag] Exception: {e}")
            return None

    def search_engine_employee_estimate(self, company_name: str, num_results: int = 5) -> int | None:
        """
        1) Try queries like '"Name" "number of employees"'
        2) Look in <li.b_algo> blocks for matching patterns
        3) Return the most‐common or max
        """
        try:
            queries = [
                f'"{company_name}" "number of employees"',
                f'"{company_name}" employees company size',
                f'"{company_name}" headcount staff size',
                f'site:linkedin.com/company/{company_name.lower().replace(" ", "-")} employees'
            ]

            url = "https://www.bing.com/search"
            all_counts: list[int] = []

            for query in queries:
                logger.info(f"[SearchEngine] Trying query: {query}")
                params = {"q": query, "count": num_results}
                r = self.session.get(url, params=params, timeout=10)
                if r.status_code != 200:
                    logger.info(f"[SearchEngine] Bing returned {r.status_code} for '{query}'")
                    continue

                soup = BeautifulSoup(r.text, "html.parser")
                for idx, block in enumerate(soup.select("li.b_algo"), start=1):
                    title_elem = block.select_one("h2 a")
                    snippet_elem = block.select_one(".b_caption p")
                    title = title_elem.get_text(" ", strip=True) if title_elem else ""
                    snippet = snippet_elem.get_text(" ", strip=True) if snippet_elem else ""
                    combined = f"{title} {snippet}"
                    if company_name.lower() not in combined.lower():
                        continue

                    logger.info(f"[SearchEngine] Snippet #{idx}: '{snippet}'")
                    patterns = [
                        r"(\d[\d,]*)\s+(?:employees?|staff|people)",
                        r"has\s+(\d[\d,]*)\s+(?:employees?|staff)",
                        r"employs\s+(\d[\d,]*)",
                        r"team\s+of\s+(\d[\d,]*)",
                        r"(\d[\d,]*)\s*-\s*(?:person|employee|staff)",
                        r"over\s+(\d[\d,]*)\s+(?:employees?|people)",
                        r"more\s+than\s+(\d[\d,]*)\s+(?:employees?|people)"
                    ]
                    for pattern in patterns:
                        for match in re.findall(pattern, combined, re.IGNORECASE):
                            try:
                                val = int(match.replace(",", ""))
                                if 1 <= val <= 1_000_000:
                                    logger.info(f"[SearchEngine] Found match {val} via '{pattern}'.")
                                    all_counts.append(val)
                            except ValueError:
                                continue

                time.sleep(1)

            if not all_counts:
                logger.info(f"[SearchEngine] No valid employee count found.")
                return None

            freq = Counter(all_counts)
            logger.info(f"[SearchEngine] Collected counts: {dict(freq)}")
            most_common, freq_count = freq.most_common(1)[0]
            return most_common if freq_count > 1 else max(all_counts)

        except Exception as e:
            logger.warning(f"[SearchEngine] Exception for '{company_name}': {e}")
            return None

    def scrape_site_for_employees(self, company_domain: str) -> int | None:
        """
        1) Look for team/leadership pages
        2) Then contact/about pages
        3) Then footer or address tags
        """
        try:
            homepage_url = f"https://{company_domain}"
            html, soup_home = self.fetch_html_with_fallback(homepage_url)
            if not soup_home or not html:
                logger.info(f"[SiteScrape] Cannot fetch homepage '{homepage_url}'.")
                return None

            # 1) Team pages
            team_urls: list[str] = []
            for a in soup_home.select("a[href]"):
                href = a["href"].lower()
                text = a.get_text().lower()
                if any(keyword in href or keyword in text for keyword in ["team", "leadership", "about-us", "staff"]):
                    full_url = urljoin(homepage_url, a["href"])
                    team_urls.append(full_url)
                    logger.info(f"[SiteScrape] Potential team link: {full_url}")

            for team_url in team_urls[:3]:
                count = self.extract_team_count(team_url)
                if count and count > 1:
                    logger.info(f"[SiteScrape] Found {count} employees via '{team_url}'.")
                    return count
                else:
                    logger.info(f"[SiteScrape] No team count from '{team_url}'.")

            # 2) Contact/about pages
            contact_url = self.find_contact_link(soup_home, homepage_url)
            if contact_url:
                contact_html, soup_contact = self.fetch_html_with_fallback(contact_url)
                if soup_contact:
                    val1 = self.extract_from_about_or_contact(soup_contact)
                    if val1:
                        logger.info(f"[SiteScrape] Found {val1} via text on '{contact_url}'.")
                        return val1
                    val2 = self.extract_from_address_tag(soup_contact)
                    if val2:
                        logger.info(f"[SiteScrape] Found {val2} via <address> on '{contact_url}'.")
                        return val2
                else:
                    logger.info(f"[SiteScrape] Could not parse contact page '{contact_url}'.")
            else:
                logger.info(f"[SiteScrape] No contact link on '{homepage_url}'.")

            # 3) Footer
            footer = soup_home.find("footer")
            if footer:
                val3 = self.extract_from_about_or_contact(footer)
                if val3:
                    logger.info(f"[SiteScrape] Found {val3} in homepage footer.")
                    return val3
                else:
                    logger.info(f"[SiteScrape] No employees count in footer.")

            else:
                logger.info(f"[SiteScrape] No <footer> on '{homepage_url}'.")

            logger.info(f"[SiteScrape] No employee count found on site '{company_domain}'.")
            return None

        except Exception as e:
            logger.warning(f"[SiteScrape] Exception for domain '{company_domain}': {e}")
            return None

    def get_employee_count(self, company_name: str) -> int | None:
        """
        1) Try Wikidata
        2) Try Wikipedia infobox
        3) Try search‐engine snippet patterns
        4) Try direct site scraping
        """
        logger.info(f"Starting employee‐count lookup for: '{company_name}'")

        # Step 1: Wikidata
        logger.info("→ Step 1: Trying Wikidata…")
        wd_val = self.query_wikidata_employees(company_name)
        if wd_val is not None:
            logger.info(f"→ [Result] {company_name}: {wd_val} (via Wikidata)")
            return wd_val

        # Step 2: Wikipedia
        logger.info("→ Step 2: Trying Wikipedia infobox…")
        wiki_val = self.parse_wikipedia_infobox_employees(company_name)
        if wiki_val is not None:
            logger.info(f"→ [Result] {company_name}: {wiki_val} (via Wikipedia)")
            return wiki_val

        # Step 3: Search‐engine snippets
        logger.info("→ Step 3: Trying search engine snippet extraction…")
        se_val = self.search_engine_employee_estimate(company_name)
        if se_val is not None:
            logger.info(f"→ [Result] {company_name}: {se_val} (via search engine snippets)")
            return se_val

        # Step 4: Direct site scraping
        logger.info("→ Step 4: Trying direct website scraping…")
        domain = self.find_verified_domain(company_name)
        if domain:
            logger.info(f"[Main] Using domain: {domain}")
            site_val = self.scrape_site_for_employees(domain)
            if site_val is not None:
                logger.info(f"→ [Result] {company_name}: {site_val} (via direct site scraping)")
                return site_val
            else:
                logger.info(f"[Main] No employee count found on site '{domain}'.")
        else:
            logger.info(f"[Main] Could not verify any domain for '{company_name}'.")

        logger.info(f"→ [Result] {company_name}: No employee count found in any source.")
        return None
