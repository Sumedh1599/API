from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
from playwright.async_api import async_playwright
from fastapi.security import APIKeyHeader
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import time

# API Key Configuration
API_KEY = "sumedh1599_secret_key_xyz"
API_KEY_NAME = "x-api-key"

# Define API key dependency
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def validate_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for cross-origin requests
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

# Enhanced job scraping function
async def scrape_jobs(company, country):
    results = []
    query = "%20".join(company.split())  # Format the query for URL
    url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={country}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context()
        page = await context.new_page()

        # Mimic human-like behavior
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            """
        )

        try:
            await page.goto(url, timeout=60000)

            # Handle potential login/security challenge
            if "security/challenge" in page.url:
                raise HTTPException(status_code=403, detail="LinkedIn security check triggered. Cannot proceed.")

            # Scrape jobs from multiple pages
            while True:
                try:
                    await page.wait_for_selector(".base-card", timeout=20000)
                except Exception:
                    print("No job cards found on this page. Ending scrape.")
                    break

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

                        if company.lower().strip() != company_name.lower().strip():
                            continue

                        description = "Description not available"
                        if apply_link != "N/A":
                            try:
                                job_page = await context.new_page()
                                await job_page.goto(apply_link, timeout=60000)
                                await asyncio.sleep(random.uniform(3, 6))  # Mimic human browsing delay

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
                    except Exception as card_err:
                        print(f"Error processing a job card: {card_err}")

                next_button = await page.query_selector("button[aria-label='Next']")
                if next_button and await next_button.is_enabled():
                    await asyncio.sleep(random.uniform(4, 8))  # Mimic human delay
                    try:
                        await next_button.click(timeout=15000)
                        await page.wait_for_load_state("networkidle")
                    except Exception as click_err:
                        print(f"Error clicking next button: {click_err}")
                        break
                else:
                    break

        except Exception as main_err:
            print(f"Main scraping error: {main_err}")
            raise HTTPException(status_code=500, detail=str(main_err))
        finally:
            await context.close()
            await browser.close()

    return results

# API endpoint for job search with API key validation
@app.post("/search_jobs/", dependencies=[Depends(validate_api_key)])
async def search_jobs(request: JobSearchRequest):
    company = request.company
    country = request.country
    jobs = await scrape_jobs(company, country)
    return {"jobs": jobs}

# Add security scheme for API key in the documentation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="LinkedIn Job Scraper API",
        version="0.3.0",
        description="An advanced API to scrape LinkedIn job postings with enhanced human-like behavior and maximum data extraction.",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "name": API_KEY_NAME,
            "in": "header",
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
