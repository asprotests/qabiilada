import aiohttp
import asyncio
import json
import re
import os
import requests
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm

CONCURRENT_REQUESTS = 10
TOTAL_IDS = 34332
DATA_FILE = "abtirsi_data.jsonl"
FAILED_FILE = "abtirsi_failed.json"

semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
written_ids = set()
failed_ids = set()
results = []

ROOT_CLANS = [
    {"name": "Darod", "id": 1},
    {"name": "Dir", "id": 158},
    {"name": "Hawiye", "id": 572},
    {"name": "Digil", "id": 648},
    {"name": "Mirifle", "id": 651},
    {"name": "Ajuran", "id": 1595},
    {"name": "Saransor", "id": 820},
    {"name": "Omar Garre", "id": 147},
    {"name": "Yusuf AlKawnayn", "id": 858},
    {"name": "Sheikh Ishaq", "id": 1000},
    {"name": "Fiqi Omar", "id": 1251},
    {"name": "Oromo Horo", "id": 1366},
    {"name": "Hasan Kawayni", "id": 1775}
]

def get_homepage_ids():
    print("🔍 Extracting root-level clan IDs from homepage...")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://www.abtirsi.com", headers=headers)
        if r.status_code != 200:
            print(f"❌ Failed to fetch homepage: HTTP {r.status_code}")
            return set()
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return set()

    soup = BeautifulSoup(r.text, "html.parser")
    ids = set()
    for a in soup.select("ul li a[href*='view.php?person=']"):
        match = re.search(r'person=(\d+)', a["href"])
        if match:
            ids.add(int(match.group(1)))
    print(f"✅ Found {len(ids)} extra root IDs from homepage")
    return ids

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                written_ids.add(obj["id"])
                results.append(obj)
            except:
                continue

def clean_name(name):
    if not name: return ""
    name = name.replace('\\"', '"').replace("\\'", "'")
    name = re.sub(r"[\"']", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

def parse_person_page(html, person_id):
    soup = BeautifulSoup(html, "html.parser")
    h2 = soup.find("h2", itemprop="name")
    full_name = " ".join(h2.stripped_strings) if h2 else "Unknown"
    full_name = clean_name(full_name)

    children_groups = []
    for h4 in soup.find_all("h4"):
        if "Children born by" in h4.get_text():
            mother_tag = h4.find("a")
            mother = " ".join(mother_tag.stripped_strings) if mother_tag else "???"
            mother = clean_name(mother)

            ol = h4.find_next_sibling("ol")
            children = []
            if ol:
                for li in ol.find_all("li"):
                    a = li.find("a", href=True)
                    if a:
                        child_name = " ".join(a.stripped_strings)
                        child_name = clean_name(child_name)
                        match = re.search(r'person=(\d+)', a['href'])
                        child_id = int(match.group(1)) if match else None
                        children.append({"name": child_name, "id": child_id})

            children_groups.append({"mother": mother, "children": children})

    return {
        "id": person_id,
        "name": full_name,
        "children_groups": children_groups
    }

async def fetch_and_store(session, person_id, max_retries=6):
    url = f"https://www.abtirsi.com/view.php?person={person_id}"
    attempt = 0

    while attempt < max_retries:
        try:
            async with semaphore:
                async with session.get(url, timeout=20) as resp:
                    html = await resp.text()

                    if "Resource Limit Is Reached" in html:
                        attempt += 1
                        wait = min(60 + attempt * 10, 180)
                        print(f"⏳ Overloaded at {person_id}, attempt {attempt}, waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue

                    if resp.status == 404:
                        failed_ids.add(person_id)
                        return

                    if resp.status != 200:
                        attempt += 1
                        wait = min(5 + attempt * 3, 30)
                        print(f"⚠️ HTTP {resp.status} for ID {person_id}, retry {attempt}, wait {wait}s")
                        await asyncio.sleep(wait)
                        continue

                    data = parse_person_page(html, person_id)
                    with open(DATA_FILE, "a", encoding="utf-8") as f:
                        f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    results.append(data)
                    written_ids.add(person_id)
                    return

        except Exception as e:
            attempt += 1
            wait = min(5 * attempt, 60)
            print(f"❌ Error at {person_id}: {e}, retry {attempt}, waiting {wait}s...")
            await asyncio.sleep(wait)

    print(f"❌ Giving up on {person_id} after {max_retries} retries.")
    failed_ids.add(person_id)

async def main():
    print("🚀 Scraper starting...")
    homepage_ids = get_homepage_ids()
    all_possible_ids = set(range(1, TOTAL_IDS + 1)).union(homepage_ids)
    remaining_ids = sorted(all_possible_ids - written_ids)

    async with aiohttp.ClientSession() as session:
        for i in tqdm(range(0, len(remaining_ids), CONCURRENT_REQUESTS)):
            batch = remaining_ids[i:i+CONCURRENT_REQUESTS]
            tasks = [fetch_and_store(session, pid) for pid in batch]
            await asyncio.gather(*tasks)
            await asyncio.sleep(1)

    print("🌳 Inserting Soomaali root...")
    soomaali = {
        "id": 0,
        "name": "Soomaali",
        "children_groups": [{
            "mother": "unknown",
            "children": ROOT_CLANS
        }]
    }

    if 0 not in written_ids:
        with open(DATA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(soomaali, ensure_ascii=False) + "\n")

    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(failed_ids)), f, indent=2)

    print(f"✅ Done. {len(written_ids)} entries saved.")

if __name__ == "__main__":
    asyncio.run(main())
