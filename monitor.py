"""
Surveille staff.topivo.fr et envoie une notification ntfy
dès qu'une nouvelle mission / un nouvel événement apparaît.

Variables d'environnement (à mettre dans les secrets GitHub) :
  TOPIVO_EMAIL      identifiant de connexion
  TOPIVO_PASSWORD   mot de passe
  NTFY_TOPIC        nom du canal ntfy (choisis un nom difficile à deviner)
Optionnelles :
  LOGIN_URL         page de connexion (défaut : https://staff.topivo.fr/)
  MISSIONS_URL      page qui liste les missions (défaut : /event?type=new)
  MISSION_SELECTOR  sélecteur CSS d'une mission (défaut : .card-event)
  DEBUG             "1" pour enregistrer capture d'écran + HTML dans debug/
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from playwright.sync_api import sync_playwright

LOGIN_URL = os.environ.get("LOGIN_URL", "").strip() or "https://staff.topivo.fr/"
MISSIONS_URL = os.environ.get("MISSIONS_URL", "").strip() or "https://staff.topivo.fr/event?type=new"
SELECTOR = os.environ.get("MISSION_SELECTOR", "").strip() or ".card-event"
EMAIL = os.environ["TOPIVO_EMAIL"]
PASSWORD = os.environ["TOPIVO_PASSWORD"]
TOPIC = os.environ["NTFY_TOPIC"]
DEBUG = os.environ.get("DEBUG") == "1"

STATE_FILE = Path("state.json")
DEBUG_DIR = Path("debug")


def notify(title, message, click=None, priority=4, tags=None):
    payload = {"topic": TOPIC, "title": title, "message": message,
               "priority": priority, "tags": tags or ["stadium"]}
    if click:
        payload["click"] = click
    requests.post("https://ntfy.sh/", json=payload, timeout=20).raise_for_status()


def h(s):
    # On ne stocke que des empreintes : rien de lisible dans le dépôt
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen": [], "initialized": False, "error_notified": False}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True))


def login(page):
    page.goto(LOGIN_URL, wait_until="networkidle")
    pwd = page.locator("input[type=password]").first
    if pwd.count() == 0:
        # Peut-être un bouton "Se connecter" à cliquer d'abord
        for txt in ["Se connecter", "Connexion", "Login", "Sign in"]:
            btn = page.get_by_text(txt, exact=False).first
            if btn.count():
                btn.click()
                page.wait_for_load_state("networkidle")
                break
        pwd = page.locator("input[type=password]").first
    user = page.locator(
        "input[type=email], input[name*=mail i], input[name*=user i], "
        "input[name*=login i], input[type=text]"
    ).first
    user.fill(EMAIL)
    pwd.fill(PASSWORD)
    pwd.press("Enter")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    if page.locator("input[type=password]").count() and page.locator("input[type=password]").first.is_visible():
        raise RuntimeError("Connexion échouée (le formulaire est toujours affiché)")


def collect_missions(page):
    if MISSIONS_URL:
        page.goto(MISSIONS_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)
    if SELECTOR:
        items = page.locator(SELECTOR).all()
        out = []
        for it in items:
            lines = [l.strip() for l in it.inner_text().splitlines()]
            lines = [l for l in lines if l and l.lower() not in ("new", "go")]
            # ex : "Stade de la Meinau - RCSA/BREST - 21.11.26 · Strasbourg · sam. 21 novembre 2026"
            text = " · ".join(lines[1:] if len(lines) > 1 and len(lines[0]) < 15 else lines)[:200]
            link = it.get_attribute("href") or (
                it.locator("a[href]").first.get_attribute("href")
                if it.locator("a[href]").count() else None)
            key = link or text
            if key:
                out.append({"key": key, "text": text,
                            "url": urljoin(page.url, link) if link else page.url})
        return out
    # Mode générique : tous les liens hors menus / en-tête / pied de page
    raw = page.evaluate("""() => [...document.querySelectorAll('a[href]')]
        .filter(a => !a.closest('nav, header, footer, aside'))
        .map(a => ({href: a.href, text: a.innerText.replace(/\\s+/g,' ').trim()}))""")
    out, seen = [], set()
    for r in raw:
        href = r["href"].split("#")[0]
        if not href.startswith("http") or href in seen or not r["text"]:
            continue
        if any(x in href.lower() for x in ["logout", "deconnexion", "profil", "account", "mailto:"]):
            continue
        seen.add(href)
        out.append({"key": href, "text": r["text"][:200], "url": href})
    return out


def main():
    state = load_state()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="fr-FR")
        try:
            login(page)
            missions = collect_missions(page)
            if DEBUG:
                DEBUG_DIR.mkdir(exist_ok=True)
                page.screenshot(path=str(DEBUG_DIR / "page.png"), full_page=True)
                (DEBUG_DIR / "page.html").write_text(page.content())
                (DEBUG_DIR / "missions.json").write_text(json.dumps(missions, indent=1, ensure_ascii=False))
        except Exception as e:
            if DEBUG:
                DEBUG_DIR.mkdir(exist_ok=True)
                page.screenshot(path=str(DEBUG_DIR / "erreur.png"), full_page=True)
            if not state.get("error_notified"):
                notify("Topivo : le script ne marche plus", str(e)[:300], priority=3, tags=["warning"])
                state["error_notified"] = True
                save_state(state)
            raise
        finally:
            browser.close()

    state["error_notified"] = False
    seen = set(state["seen"])
    new = [m for m in missions if h(m["key"]) not in seen]
    print(f"{len(missions)} éléments trouvés, {len(new)} nouveaux")

    if not state["initialized"]:
        notify("Topivo : surveillance activée",
               f"{len(missions)} missions déjà en ligne. Je te préviens dès qu'une nouvelle apparaît.",
               priority=2, tags=["white_check_mark"])
        state["initialized"] = True
    elif new:
        if len(new) == 1:
            notify("Nouvelle mission Topivo !", new[0]["text"], click=new[0]["url"], priority=5)
        else:
            lines = "\n".join("• " + m["text"] for m in new[:8])
            notify(f"{len(new)} nouvelles missions Topivo !", lines, click=new[0]["url"], priority=5)

    state["seen"] = sorted(seen | {h(m["key"]) for m in missions})
    save_state(state)


if __name__ == "__main__":
    sys.exit(main())
