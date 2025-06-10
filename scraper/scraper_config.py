FAKE_CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.5735.198 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

GENERIC_WORDS = {
    'inc', 'llc', 'biotech', 'corp', 'corporation',
    'company', 'group', 'co', 'ltd', 'plc', 'therapeutics',
    'pharmaceuticals', 'technologies', 'systems', 'solutions', 'labs', 'laboratories'
}

SKIP_DOMAINS = {
    'bing.com', 'linkedin.com', 'wikipedia.org', 'facebook.com',
    'twitter.com', 'crunchbase.com'
}

BIOTECH_TERMS = {
    'biotech', 'therapeutics', 'biosciences', 'life sciences',
    'pharma', 'cell therapy', 'rna', 'genomics', 'gene therapy', 'biologic'
}

ACQUISITION_KEYWORDS = [
    "acquired by", "is now part of", "a subsidiary of",
    "acquisition by", "now belongs to", "merged with",
    "is part of", "wholly owned by", "purchased by",
    "bought by", "taken over by", "absorbed by"
]

ACQUISITION_MAP = {
    "Seagen": "Pfizer",
    "Neogene Therapeutics": "Illumina",
}
