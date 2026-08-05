"""Fetch PlayStation trophy stats and write data/psn_stats.json.

Auth: PSN_NPSSO env var — the npsso cookie from ca.account.sony.com/api/v1/ssocookie,
stored as a GitHub Actions secret. Flow (as documented by the psn-api project):
npsso -> authorization code -> access token -> m.np.playstation.com API.

Privacy: only aggregate counts and game titles are written to the public file.
No username, online ID, or account ID is ever included.
Stdlib only.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "psn_stats.json"

CLIENT_ID = "09515159-7237-4370-9b40-3806e67c0891"
CLIENT_AUTH = "MDk1MTUxNTktNzIzNy00MzcwLTliNDAtMzgwNmU2N2MwODkxOnVjUGprYTV0bnRCMktxc1A="
REDIRECT = "com.scee.psxandroid.scecompcall://redirect"
N_GAMES = 5


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get_access_token(npsso):
    params = urllib.parse.urlencode({
        "access_type": "offline",
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "psn:mobile.v2.core psn:clientapp",
        "redirect_uri": REDIRECT,
    })
    req = urllib.request.Request(
        f"https://ca.account.sony.com/api/authz/v3/oauth/authorize?{params}",
        headers={"Cookie": f"npsso={npsso}", "User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(req, timeout=30)
        print("authorize: expected a redirect but got none")
        return None
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location", "")
    code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query).get("code", [None])[0]
    if not code:
        print(f"authorize: no code in redirect ({location[:80]}...) — npsso expired?")
        return None

    body = urllib.parse.urlencode({
        "code": code,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
        "token_format": "jwt",
    }).encode()
    req = urllib.request.Request(
        "https://ca.account.sony.com/api/authz/v3/oauth/token", data=body,
        headers={"Authorization": f"Basic {CLIENT_AUTH}",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("access_token")


def api(path, token):
    req = urllib.request.Request(
        f"https://m.np.playstation.com/api/{path}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    npsso = os.environ.get("PSN_NPSSO", "").strip()
    if not npsso:
        print("PSN_NPSSO env var not set")
        return 1

    token = get_access_token(npsso)
    if not token:
        return 1
    print("auth ok")

    summary = api("trophy/v1/users/me/trophySummary", token)
    earned = summary.get("earnedTrophies", {})
    out = {
        "level": summary.get("trophyLevel"),
        "trophies": {
            "platinum": earned.get("platinum", 0),
            "gold": earned.get("gold", 0),
            "silver": earned.get("silver", 0),
            "bronze": earned.get("bronze", 0),
        },
    }
    print(f"summary ok: level {out['level']}")

    titles = api(f"trophy/v1/users/me/trophyTitles?limit={N_GAMES}", token)
    out["recent"] = [{
        "name": t.get("trophyTitleName", ""),
        "platform": t.get("trophyTitlePlatform", ""),
        "icon": t.get("trophyTitleIconUrl", ""),
        "earned": sum((t.get("earnedTrophies") or {}).values()),
        "total": sum((t.get("definedTrophies") or {}).values()),
        "progress": t.get("progress", 0),
        "last_played": (t.get("lastUpdatedDateTime") or "")[:10],
    } for t in titles.get("trophyTitles", [])]
    print(f"titles ok: {len(out['recent'])} recent games")

    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
