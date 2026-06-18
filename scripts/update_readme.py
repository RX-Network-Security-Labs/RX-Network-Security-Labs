import os, json, re, urllib.request, urllib.error
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

USERNAME = "RX-Network-Security-Labs"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

QUOTES = [
    ("Privacy is not something I'm merely entitled to — it's an absolute prerequisite.", "Marlon Brando"),
    ("Arguing that you don't care about privacy because you have nothing to hide is no different than saying you don't care about free speech because you have nothing to say.", "Edward Snowden"),
    ("Surveillance is the business model of the internet.", "Bruce Schneier"),
    ("We should treat personal electronic data with the same care and respect as we treat sensitive documents.", "Tim Berners-Lee"),
    ("Privacy is the foundation of all other rights.", "Glenn Greenwald"),
    ("Security is not a product, but a process.", "Bruce Schneier"),
    ("Encryption works. Properly implemented strong crypto systems are one of the few things you can rely on.", "Edward Snowden"),
    ("The only truly secure system is one that is powered off.", "Gene Spafford"),
    ("If you think technology can solve your security problems, then you don't understand the problems and you don't understand the technology.", "Bruce Schneier"),
    ("You have zero privacy anyway. Get over it.", "Scott McNealy — and exactly why we exist."),
]

def gh_request(url):
    headers = {"User-Agent": "RNSL-Bot", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [WARN] {url} → {e}")
        return None

def fetch_repos():
    repos, page = [], 1
    while True:
        data = gh_request(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}")
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return [r for r in repos if r["name"] != USERNAME and not r.get("fork")]

def fetch_topics(repo_name):
    headers = {"User-Agent": "RNSL-Bot", "Accept": "application/vnd.github.mercy-preview+json"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    req = urllib.request.Request(
        f"https://api.github.com/repos/{USERNAME}/{repo_name}/topics",
        headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("names", [])
    except:
        return []

def fetch_latest_release(repo_name):
    data = gh_request(f"https://api.github.com/repos/{USERNAME}/{repo_name}/releases/latest")
    if data and "tag_name" in data:
        return {
            "repo": repo_name,
            "tag": data["tag_name"],
            "name": data.get("name") or data["tag_name"],
            "url": data["html_url"],
            "date": data["published_at"][:10],
            "body": (data.get("body") or "").split("\n")[0][:80],
        }
    return None

def fetch_security_advisories():
    advisories = []
    repos_data = gh_request(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
    if not repos_data:
        return advisories
    for repo in repos_data:
        data = gh_request(f"https://api.github.com/repos/{USERNAME}/{repo['name']}/security-advisories")
        if data and isinstance(data, list):
            for adv in data[:2]:
                advisories.append({
                    "repo": repo["name"],
                    "title": adv.get("summary", "Advisory"),
                    "severity": adv.get("severity", "unknown").upper(),
                    "url": adv.get("html_url", "#"),
                    "date": (adv.get("published_at") or "")[:10],
                    "state": adv.get("state", ""),
                })
    return advisories[:5]

def fetch_telegram_latest():
    try:
        url = "https://tg.i-c-a.su/rss/rxnetworksecuritylabs"
        req = urllib.request.Request(url, headers={"User-Agent": "RNSL-Bot"})
        with urllib.request.urlopen(req, timeout=10) as r:
            root = ET.fromstring(r.read())
        ns = ""
        items = root.findall(f".//{ns}item")
        if not items:
            return None
        item = items[0]
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        date  = (item.findtext("pubDate") or "")[:16].strip()
        desc  = (item.findtext("description") or "").strip()
        # Strip HTML tags roughly
        desc = re.sub(r"<[^>]+>", "", desc)[:120].strip()
        return {"title": title, "link": link, "date": date, "desc": desc}
    except Exception as e:
        print(f"  [WARN] Telegram RSS → {e}")
        return None

def fetch_org_stats(repos):
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    total_watchers = sum(r.get("watchers_count", 0) for r in repos)
    languages = {}
    for r in repos:
        l = r.get("language")
        if l:
            languages[l] = languages.get(l, 0) + 1
    top_lang = max(languages, key=languages.get) if languages else "—"
    return {
        "repos": len(repos),
        "stars": total_stars,
        "forks": total_forks,
        "watchers": total_watchers,
        "top_lang": top_lang,
    }

def lang_badge(lang):
    colors = {
        "Python":"3776AB","JavaScript":"F7DF1E","TypeScript":"3178C6",
        "Shell":"89e051","Kotlin":"7F52FF","Java":"ED8B00",
        "C":"555555","C++":"f34b7d","Go":"00ADD8","Rust":"dea584",
    }
    if not lang:
        return ""
    color = colors.get(lang, "2ecc71")
    safe = lang.replace("-","--").replace(" ","_").replace("+","%2B")
    return f"![{lang}](https://img.shields.io/badge/-{safe}-{color}?style=flat-square)"

def repo_row(repo):
    name  = repo["name"]
    desc  = (repo.get("description") or "—")[:70]
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    url   = repo.get("html_url", "#")
    upd   = repo.get("updated_at", "")[:10]
    lb    = lang_badge(repo.get("language"))
    return f"| [`{name}`]({url}) | {desc} | {lb} | ⭐ {stars} &nbsp; 🍴 {forks} | `{upd}` |"

TABLE_HEADER = "| Repository | Description | Language | Stats | Updated |\n|---|---|---|---|---|\n"

def build_repo_section(repo_list, empty):
    if not repo_list:
        return f"> {empty}"
    return TABLE_HEADER + "\n".join(repo_row(r) for r in repo_list)

def build_releases_section(repos):
    releases = []
    for r in repos:
        rel = fetch_latest_release(r["name"])
        if rel:
            releases.append(rel)
    releases.sort(key=lambda x: x["date"], reverse=True)
    releases = releases[:5]
    if not releases:
        return "> No releases yet — first drop incoming."
    rows = "| Repository | Release | Notes | Date |\n|---|---|---|---|\n"
    for rel in releases:
        notes = rel["body"] or "—"
        rows += f"| [`{rel['repo']}`]({rel['url']}) | `{rel['tag']}` · {rel['name']} | {notes} | `{rel['date']}` |\n"
    return rows

def build_advisories_section(advisories):
    if not advisories:
        return "> No public security advisories at this time."
    severity_badge = {
        "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡",
        "LOW": "🟢", "UNKNOWN": "⚪"
    }
    rows = "| Repository | Advisory | Severity | Status | Date |\n|---|---|---|---|---|\n"
    for adv in advisories:
        icon = severity_badge.get(adv["severity"], "⚪")
        rows += f"| `{adv['repo']}` | [{adv['title']}]({adv['url']}) | {icon} {adv['severity']} | `{adv['state']}` | `{adv['date']}` |\n"
    return rows

def build_telegram_section(post):
    if not post:
        return "> Could not fetch latest post — [visit our channel](https://t.me/rxnetworksecuritylabs)"
    return f"""📨 **[{post['title'] or 'Latest Post'}]({post['link']})**
> {post['desc']}
>
> `{post['date']}` · [View on Telegram →](https://t.me/rxnetworksecuritylabs)"""

def build_achievements_section(stats, repos):
    milestone = lambda val, steps: next((s for s in steps if val < s), steps[-1])
    star_next  = milestone(stats["stars"],  [10,50,100,500,1000,5000])
    repo_next  = milestone(stats["repos"],  [5,10,25,50,100])
    fork_next  = milestone(stats["forks"],  [10,50,100,500])

    def bar(current, target, width=20):
        filled = min(int((current / target) * width), width)
        return "█" * filled + "░" * (width - filled)

    return f"""```
╔══════════════════════════════════════════════════════╗
║               RNSL  ACHIEVEMENTS                     ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  📦  Repositories   {str(stats['repos']).rjust(4)}   {bar(stats['repos'], repo_next)}  → {repo_next}  ║
║  ⭐  Total Stars    {str(stats['stars']).rjust(4)}   {bar(stats['stars'], star_next)}  → {star_next}  ║
║  🍴  Total Forks    {str(stats['forks']).rjust(4)}   {bar(stats['forks'], fork_next)}  → {fork_next}  ║
║  👁️  Watchers       {str(stats['watchers']).rjust(4)}                                  ║
║  🔤  Primary Lang   {stats['top_lang'].ljust(10)}                            ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```"""

def build_quote_section():
    day = datetime.now(timezone.utc).timetuple().tm_yday
    quote, author = QUOTES[day % len(QUOTES)]
    return f'> *"{quote}"*\n>\n> — **{author}**'

def update_section(content, name, new_content):
    s = f"<!--START_SECTION:{name}-->"
    e = f"<!--END_SECTION:{name}-->"
    return re.sub(
        rf"{re.escape(s)}.*?{re.escape(e)}",
        f"{s}\n{new_content}\n{e}",
        content, flags=re.DOTALL
    )

def main():
    print("=== RNSL README Updater ===")
    print("Fetching repos...")
    all_repos = fetch_repos()
    print(f"  Found {len(all_repos)} repos")

    apps, tools, services, research = [], [], [], []
    for repo in all_repos:
        topics = fetch_topics(repo["name"])
        if   "rnsl-app"      in topics: apps.append(repo)
        elif "rnsl-tool"     in topics: tools.append(repo)
        elif "rnsl-service"  in topics: services.append(repo)
        elif "rnsl-research" in topics: research.append(repo)

    print("Fetching releases...")
    print("Fetching security advisories...")
    advisories = fetch_security_advisories()
    print("Fetching Telegram latest post...")
    tg_post = fetch_telegram_latest()
    stats = fetch_org_stats(all_repos)

    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    content = update_section(content, "apps",       build_repo_section(apps,     "No apps released yet — stay tuned."))
    content = update_section(content, "tools",      build_repo_section(tools,    "Tools dropping soon."))
    content = update_section(content, "services",   build_repo_section(services, "Services coming soon."))
    content = update_section(content, "research",   build_repo_section(research, "Research & writeups coming soon."))
    content = update_section(content, "releases",   build_releases_section(all_repos))
    content = update_section(content, "advisories", build_advisories_section(advisories))
    content = update_section(content, "telegram",   build_telegram_section(tg_post))
    content = update_section(content, "achievements", build_achievements_section(stats, all_repos))
    content = update_section(content, "quote",      build_quote_section())
    content = update_section(content, "timestamp",  f"`Last synced: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✓ Done! Apps:{len(apps)} Tools:{len(tools)} Services:{len(services)} Research:{len(research)}")
    print(f"  Stars:{stats['stars']} Forks:{stats['forks']} Advisories:{len(advisories)}")

if __name__ == "__main__":
    main()
