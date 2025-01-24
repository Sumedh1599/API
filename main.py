from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from playwright.async_api import async_playwright
from playwright_stealth import stealth_sync
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random

# API Key Configuration
API_KEY = "sumedh1599_secret_key_xyz"
API_KEY_NAME = "x-api-key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def validate_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JobSearchRequest(BaseModel):
    company: str
    country: str

async def scrape_jobs(company, country):
    results = []
    query = "%20".join(company.split())
    url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={country}"

    async with async_playwright() as p:
        proxy = "http://username:password@proxy-address:port"  # Replace with your proxy credentials
        browser = await p.chromium.launch(
            headless=True,
            args=[
                f"--proxy-server={proxy}",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            locale="en-US",
        )
        page = await context.new_page()
        await stealth_sync(page)

        try:
            await page.goto(url, timeout=60000)

            for _ in range(15):  # Scroll 15 times
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2, 4))
            
            await page.wait_for_timeout(5000)

            while True:
                job_cards = await page.query_selector_all(".base-card")
                for job_card in job_cards:
                    try:
                        title = await job_card.query_selector(".base-search-card__title")
                        company_name = await job_card.query_selector(".base-search-card__subtitle")
                        location = await job_card.query_selector(".job-search-card__location")
                        apply_link = await job_card.query_selector("a.base-card__full-link")

                        title = await title.evaluate("el => el.textContent.trim()") if title else "N/A"
                        company_name = await company_name.evaluate("el => el.textContent.trim()") if company_name else "N/A"
                        location = await location.evaluate("el => el.textContent.trim()") if location else "N/A"
                        apply_link = await apply_link.get_attribute("href") if apply_link else "N/A"

                        results.append({
                            "title": title,
                            "company": company_name,
                            "location": location,
                            "apply_link": apply_link,
                        })
                    except Exception as e:
                        print(f"Error processing job card: {e}")

                next_button = await page.query_selector("button[aria-label='Next']")
                if next_button and await next_button.is_enabled():
                    await next_button.click()
                    await asyncio.sleep(random.uniform(2, 5))
                else:
                    break

        finally:
            await browser.close()

    return results

@app.post("/search_jobs/", dependencies=[Depends(validate_api_key)])
async def search_jobs(request: JobSearchRequest):
    jobs = await scrape_jobs(request.company, request.country)
    return {"jobs": jobs}
