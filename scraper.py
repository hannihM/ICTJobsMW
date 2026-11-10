import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Specific keywords to catch CS / Software / IT roles
CS_KEYWORDS = [
    "computer science", "software", "developer", "programmer", "programming",
    "python", "java", "php", "ict", "it support", "it officer",
    "it administrator", "it technician", "it manager", "information technology",
    "network", "cyber security", "cybersecurity", "systems engineer",
    "system administrator", "database", "sql", "web developer", "web master",
    "devops", "cloud engineer", "cloud architect", "full stack", "laravel",
    "data analyst", "data scientist", "data engineer", "machine learning",
    "artificial intelligence", "marketing", "social media", "graphic design",
]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

DEADLINE_PATTERN = re.compile(
    r"\b(?:application\s+deadline|application\s+closing\s+date|closing\s+date|deadline|"
    r"apply\s+before|applications?\s+close(?:s)?(?:\s+on)?)\s*[:\-]?\s*"
    r"(?P<date>(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)(?:\s*,?\s*\d{4})?|(?:Jan(?:uary)?|Feb(?:ruary)?|"
    r"Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?"
    r"(?:,?\s*\d{4})?|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}))",
    re.IGNORECASE,
)


def is_cs_related_job(title):
    """Returns whether a job title identifies a computer-science-related role."""
    title = title.lower()
    return any(re.search(rf"\b{re.escape(keyword)}\b", title) for keyword in CS_KEYWORDS)


def get_job_deadline(url, text, expired=False):
    """Returns a published deadline, an expired status, or an honest fallback."""
    if expired:
        return "Expired"

    match = DEADLINE_PATTERN.search(text)
    if match:
        return match.group("date").strip(" .,;")

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        detail_text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        match = DEADLINE_PATTERN.search(detail_text)
        if match:
            return match.group("date").strip(" .,;")
    except requests.RequestException:
        pass

    return "Not listed"


def scrape_wp_job_manager_jobs(base_url, source, id_prefix, company_fallback, location_fallback):
    """Fetches real job cards from a WordPress Job Manager listings endpoint."""
    base_url = base_url.rstrip("/")
    endpoint = f"{base_url}/jm-ajax/get_listings/"
    jobs = []
    print(f"Scraping {source}...")
    try:
        response = requests.post(
            endpoint,
            headers={
                **DEFAULT_HEADERS,
                "Referer": f"{base_url}/",
                "X-Requested-With": "XMLHttpRequest",
            },
            data={"per_page": 200, "page": 1, "orderby": "featured", "order": "DESC"},
            timeout=15,
        )
        if response.status_code != 200:
            print(f"{source} returned HTTP {response.status_code}")
            return jobs

        payload = response.json()
        max_pages = min(int(payload.get("max_num_pages", 1)), 5)
        for page in range(1, max_pages + 1):
            if page > 1:
                response = requests.post(
                    endpoint,
                    headers={
                        **DEFAULT_HEADERS,
                        "Referer": f"{base_url}/",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    data={"per_page": 200, "page": page, "orderby": "featured", "order": "DESC"},
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()

            soup = BeautifulSoup(payload.get("html", ""), "html.parser")
            for idx, card in enumerate(soup.select("li.job_listing")):
                title_elem = card.select_one(".position h3, h3")
                link_elem = card.select_one("a[href]")
                if not title_elem or not link_elem:
                    continue

                title = title_elem.get_text(" ", strip=True)
                text_content = card.get_text(separator=" ", strip=True)
                if not title or not is_cs_related_job(title):
                    continue

                link = urljoin(base_url, link_elem["href"])
                company_elem = card.select_one(".company strong")
                location_elem = card.select_one(".location")
                jobs.append({
                    "id": f"{id_prefix}-{(page - 1) * 200 + idx}",
                    "title": title,
                    "company": company_elem.get_text(" ", strip=True) if company_elem else company_fallback,
                    "location": location_elem.get_text(" ", strip=True) if location_elem else location_fallback,
                    "link": link,
                    "source": source,
                    "snippet": text_content[:180] + "..." if len(text_content) > 180 else text_content,
                    "category": categorize_job(title),
                    "deadline": get_job_deadline(link, text_content, "status-expired" in card.get("class", [])),
                })
    except Exception as e:
        print(f"Error scraping {source}: {e}")
    return jobs


def scrape_ntchito_jobs():
    """Scrapes jobs from Ntchito Malawi."""
    return scrape_wp_job_manager_jobs(
        "https://ntchito.com",
        "Ntchito Malawi",
        "ntchito",
        "Not Specified",
        "Malawi",
    )

def scrape_careers_mw():
    """Scrapes jobs from The Job Centre Malawi."""
    url = "https://careersmw.com/"
    jobs = []
    print("Scraping Job Centre Malawi...")
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if response.status_code != 200:
            return jobs
            
        soup = BeautifulSoup(response.text, "html.parser")
        # Adjust selector depending on structural layout of Job Centre cards
        job_cards = soup.find_all(["div", "article"], class_=re.compile(r'job|card|item|vacancy', re.I))
        
        for idx, card in enumerate(job_cards):
            title_elem = card.find(["h3", "h4", "a", "h2"])
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            link_elem = card.find("a", href=True)
            link = link_elem["href"] if link_elem else "#"
            if link.startswith("/"):
                link = "https://careersmw.com/" + link
                
            text_content = card.get_text(separator=" ", strip=True)
            
            if is_cs_related_job(title):
                deadline = get_job_deadline(link, text_content)
                jobs.append({
                    "id": f"careers-{idx}",
                    "title": title,
                    "company": "Verified Employer",
                    "location": "Malawi / Remote",
                    "link": link,
                    "source": "Job Centre Malawi",
                    "snippet": text_content[:180] + "..." if len(text_content) > 180 else text_content,
                    "category": categorize_job(title),
                    "deadline": deadline,
                })
    except Exception as e:
        print(f"Error scraping Job Centre Malawi: {e}")
    return jobs

def scrape_malawi_jobs():
    """Scrapes tech listings from malawi job portal."""
    return scrape_wp_job_manager_jobs(
        "https://jobsearchmalawi.com",
        "malawi Jobs",
        "malawi",
        "Various",
        "Malawi",
    )

def categorize_job(title):
    """Categorize job by domain for quick filtering."""
    t = title.lower()
    if any(k in t for k in ["developer", "software", "programmer", "web", "python", "java", "laravel"]):
        return "Software Development"
    elif any(k in t for k in ["network", "system", "infrastructure", "devops"]):
        return "Networks & Systems"
    elif any(k in t for k in ["data", "database", "sql", "analyst"]):
        return "Data & Analytics"
    elif any(k in t for k in ["support", "ict", "technician", "it officer"]):
        return "IT Operations & Support"
    return "General CS/IT"

def get_cs_jobs():
    """Aggregates job lists from all targeted Malawi platforms."""
    jobs = []
    
    # Collect from individual platform functions
    jobs.extend(scrape_ntchito_jobs())
    jobs.extend(scrape_careers_mw())
    jobs.extend(scrape_malawi_jobs())
    
    # Deduplicate entries based on title similarity or link
    seen_links = set()
    unique_jobs = []
    for job in jobs:
        if job["link"] not in seen_links:
            seen_links.add(job["link"])
            unique_jobs.append(job)
            
    # Assign sequential IDs for clean template rendering
    for i, job in enumerate(unique_jobs):
        job["id"] = i + 1

    return jobs