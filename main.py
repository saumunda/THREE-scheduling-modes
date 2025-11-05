import requests
import json
import time
import asyncio
from playwright.async_api import async_playwright

# === CONFIGURATION ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
JOB_PAGE_URL = "https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB"

# Telegram bot credentials
TELEGRAM_BOT_TOKEN = "8214392800:AAGrRksRKpAD8Oa8H4aByo5XKSwc_9SM9Bo"
CHAT_IDS = ["7943617436", "-1002622997910"]  # Send to both

# Track jobs already sent
seen_jobs = set()


# === TELEGRAM ALERT ===
def send_telegram_message(message):
    for chat_id in CHAT_IDS:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            requests.post(url, data=payload)
        except Exception as e:
            print(f"⚠️ Telegram send error to {chat_id}: {e}")


# === TOKEN FETCH USING PLAYWRIGHT (headless browser) ===
async def get_auth_token():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(JOB_PAGE_URL, wait_until="load")
            cookies = await page.context.cookies()
            await browser.close()

            for cookie in cookies:
                if "session" in cookie["name"].lower():
                    print(f"✅ Session cookie found: {cookie['name']}")
                    send_telegram_message(f"✅ Session cookie found: {cookie['name']}")
                    return f"Bearer {cookie['value']}"
    except Exception as e:
        print(f"❌ Playwright token fetch failed: {e}")
    return None


# === JOB FETCH FUNCTION ===
def fetch_jobs(auth_token):
    payload = {
        "operationName": "searchJobCardsByLocation",
        "variables": {
            "searchJobRequest": {
                "locale": "en-GB",
                "country": "United Kingdom",
                "keyWords": "Warehouse Operative",
                "equalFilters": [],
                "containFilters": [{"key": "isPrivateSchedule", "val": ["true", "false"]}],
                "rangeFilters": [],
                "orFilters": [],
                "dateFilters": [],
                "sorters": [{"fieldName": "totalPayRateMax", "ascending": "false"}],
                "pageSize": 20,
                "consolidateSchedule": True
            }
        },
        "query": """
        query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
          searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
            jobCards {
              jobId
              jobTitle
              city
              totalPayRateMax
              locationName
              totalPayRateMaxL10N
              employmentType
            }
          }
        }
        """
    }

    headers = {
        "Authorization": auth_token,
        "Content-Type": "application/json",
        "Origin": "https://www.jobsatamazon.co.uk",
        "Referer": "https://www.jobsatamazon.co.uk/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            job_cards = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
            print(f"📦 Found {len(job_cards)} jobs.")

            for job in job_cards:
                job_id = job.get("jobId")
                if job_id not in seen_jobs:
                    seen_jobs.add(job_id)
                    title = job.get("jobTitle")
                    city = job.get("city")
                    pay = job.get("totalPayRateMax")
                    msg = f"💼 *{title}* in {city}\n💰 Pay: £{pay}/hr\n🔗 https://www.jobsatamazon.co.uk/app#/jobDetail/{job_id}"
                    print("🔔 New job found:", title)
                    send_telegram_message(msg)
        else:
            print("⚠️ GraphQL request failed:", response.status_code, response.text)
    except Exception as e:
        print("⚠️ Fetch error:", e)


# === BACKGROUND JOB LOOP ===
async def main_loop():
    send_telegram_message("✅ Amazon Job Bot (Online Worker) started.")
    while True:
        print("⏳ Running scheduled job check...")
        send_telegram_message("⏳ Running scheduled job check...")
        token = await get_auth_token()
        if token:
            fetch_jobs(token)
        else:
            send_telegram_message("⚠️ Could not get session token.")
        await asyncio.sleep(3600)  # every hour


if __name__ == "__main__":
    asyncio.run(main_loop())
