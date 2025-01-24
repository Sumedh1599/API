from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from playwright.async_api import async_playwright
from playwright_stealth import stealth_sync
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import random
import asyncio

# API Key Configuration
API_KEY = "sumedh1599_secret_key_xyz"
API_KEY_NAME = "x-api-key"

# Proxy List (Update these with working proxies)
PROXY_LIST = [
    "http://proxy1:port",
    "http://proxy2:port",
    "http://proxy3:port"
]

# Define API key dependency
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def validate_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

# Initialize FastAPI app
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define request model
class JobSearchRequest(BaseModel):
    company: str
    country: str

# Advanced scraping function
async def scrape_jobs(company, country):
    results = []
    query = "%20".join(company.split())
    url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={country}"

    async with async_playwright() as p:
        for proxy in PROXY_LIST:
            try:
                print(f"Using proxy: {proxy}")
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        f"--proxy-server={proxy}",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    locale="en-US",
                )
                page = await context.new_page()
                await stealth_sync(page)  # Apply stealth mode to bypass bot detection

                await page.goto(url, timeout=60000)

                # Scroll to the bottom to load all jobs
                for _ in range(5):  # Adjust based on the number of jobs
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                    await asyncio.sleep(random.uniform(1, 2))

                # Scrape jobs
                while True:
                    try:
                        await page.wait_for_selector(".base-card", timeout=15000)
                        job_cards = await page.query_selector_all(".base-card")

                        for job_card in job_cards:
                            try:
                                title_element = await job_card.query_selector(".base-search-card__title")
                                title = await title_element.evaluate("el => el.textContent.trim()") if title_element else "N/A"

                                company_element = await job_card.query_selector(".base-search-card__subtitle")
                                company_name = await company_element.evaluate("el => el.textContent.trim()") if company_element else "N/A"

                                location_element = await job_card.query_selector(".job-search-card__location")
                                location = await location_element.evaluate("el => el.textContent.trim()") if location_element else "N/A"

                                apply_link_element = await job_card.query_selector("a.base-card__full-link")
                                apply_link = await apply_link_element.get_attribute("href") if apply_link_element else "N/A"

                                description = "Description not available"
                                if apply_link != "N/A":
                                    try:
                                        job_page = await context.new_page()
                                        await job_page.goto(apply_link, timeout=30000)
                                        await asyncio.sleep(random.uniform(1, 2))  # Mimic human browsing delay

                                        selectors = [
                                            ".show-more-less-html__markup",
                                            ".description__text",
                                            ".job-description",
                                            "#job-details",
                                            ".jobs-box__html-content"
                                        ]
                                        for selector in selectors:
                                            try:
                                                description_element = await job_page.query_selector(selector)
                                                if description_element:
                                                    description = await description_element.evaluate("el => el.textContent.trim()")
                                                    break
                                            except Exception:
                                                pass

                                        await job_page.close()
                                    except Exception as desc_err:
                                        print(f"Error fetching job description: {desc_err}")

                                results.append({
                                    "title": title.strip(),
                                    "company": company_name.strip(),
                                    "location": location.strip(),
                                    "description": description.strip(),
                                    "apply_link": apply_link,
                                })

                            except Exception as e:
                                print(f"Error processing job card: {e}")

                        # Check for next page
                        next_button = await page.query_selector("button[aria-label='Next']")
                        if next_button and await next_button.is_enabled():
                            await asyncio.sleep(random.uniform(2, 4))  # Mimic human behavior
                            await next_button.click()
                            await page.wait_for_load_state("networkidle")
                        else:
                            break  # Exit loop if no more pages
                    except Exception as e:
                        print(f"Error during scraping: {e}")
                        break

                await browser.close()
                break  # Exit proxy loop if successful
            except Exception as proxy_error:
                print(f"Proxy {proxy} failed: {proxy_error}")
                continue  # Try the next proxy

    return results

# API endpoint for job search
@app.post("/search_jobs/", dependencies=[Depends(validate_api_key)])
async def search_jobs(request: JobSearchRequest):
    company = request.company
    country = request.country
    jobs = await scrape_jobs(company, country)
    return {"jobs": jobs}
