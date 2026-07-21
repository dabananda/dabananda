"""
Fetches Dabananda's GitHub repositories and writes:
  - a public / private / total repo count summary
  - a table of every repo with its description, primary language,
    total commit count (on the default branch), and last-updated date

IMPORTANT - about private repos:
  The default `GITHUB_TOKEN` that GitHub Actions injects only has access
  to the repo the workflow runs in - it CANNOT list or read your other
  repos, public or private. To include private repos (and to see their
  descriptions/languages/commit counts), this script needs a
  Personal Access Token with at least the `repo` scope (classic) or
  `Contents: Read-only` + `Metadata: Read-only` (fine-grained), stored
  as a repository secret named PROFILE_GH_TOKEN.

  Without PROFILE_GH_TOKEN, the script falls back to the public,
  unauthenticated `/users/{username}/repos` endpoint - it will still
  work, but private repos won't be counted or listed (GitHub's public
  API has no way to even reveal how many private repos exist without
  authenticating as the owner).
"""

import os
import json
import urllib.request
from datetime import datetime, timezone

README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")

USERNAME = "dabananda"

# A personal access token with `repo` scope, stored as a secret. Falls
# back to the workflow's own GITHUB_TOKEN (public data only) if unset.
TOKEN = os.environ.get("PROFILE_GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

# Repos to leave out of the table (fork clutter, archived experiments, etc).
# Edit this list any time - just repo names, not full paths.
EXCLUDE_REPOS = {USERNAME}  # the profile repo itself shows up as a repo too


def api_request(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        headers = dict(resp.getheaders())
        body = json.loads(resp.read().decode("utf-8"))
        return body, headers


def fetch_all_repos():
    """Returns list of repo dicts. Uses the authenticated /user/repos
    endpoint (includes private repos) when a real PAT is available,
    otherwise falls back to the public repo list."""
    repos = []
    page = 1

    using_pat = bool(os.environ.get("PROFILE_GH_TOKEN"))

    if using_pat:
        base_url = "https://api.github.com/user/repos?visibility=all&affiliation=owner&per_page=100"
    else:
        base_url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100"

    while True:
        body, _ = api_request(f"{base_url}&page={page}")
        if not body:
            break
        repos.extend(body)
        if len(body) < 100:
            break
        page += 1

    return repos, using_pat


def fetch_commit_count(owner, repo, default_branch):
    """Cheap trick: ask for 1 commit per page and read the 'last' page
    number from the Link header - that number equals total commits."""
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/commits"
        f"?sha={default_branch}&per_page=1"
    )
    try:
        _, headers = api_request(url)
    except Exception:  # noqa: BLE001
        return None

    link = headers.get("Link") or headers.get("link")
    if not link:
        # No Link header means 0 or 1 commit total.
        return None

    for part in link.split(","):
        if 'rel="last"' in part:
            last_url = part[part.index("<") + 1 : part.index(">")]
            query = last_url.split("?", 1)[-1]
            for kv in query.split("&"):
                if kv.startswith("page="):
                    return int(kv.split("=")[1])
    return None


def replace_between(text, start, end, replacement):
    begin = text.index(start) + len(start)
    finish = text.index(end)
    return text[:begin] + "\n" + replacement + "\n" + text[finish:]


def replace_inline(text, start, end, replacement):
    result = []
    pos = 0
    while True:
        begin = text.find(start, pos)
        if begin == -1:
            result.append(text[pos:])
            break
        finish = text.find(end, begin)
        if finish == -1:
            result.append(text[pos:])
            break
        result.append(text[pos:begin])
        result.append(start)
        result.append(replacement)
        result.append(end)
        pos = finish + len(end)
    return "".join(result)


def main():
    repos, using_pat = fetch_all_repos()
    repos = [r for r in repos if r["name"] not in EXCLUDE_REPOS and not r.get("fork")]

    public_repos = [r for r in repos if not r.get("private")]
    private_repos = [r for r in repos if r.get("private")]

    total_count = len(repos)
    public_count = len(public_repos)
    private_count = len(private_repos)

    # Sort by most-recently-pushed first.
    repos.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)

    rows = []
    for repo in repos:
        name = repo["name"]
        description = (repo.get("description") or "_No description_").replace("|", "\\|")
        language = repo.get("language") or "—"
        visibility = "🔒 Private" if repo.get("private") else "🌐 Public"
        pushed_at = repo.get("pushed_at")
        last_updated = (
            datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
            if pushed_at
            else "—"
        )

        commits = fetch_commit_count(USERNAME, name, repo.get("default_branch") or "main")
        commits_display = str(commits) if commits is not None else "—"

        url = repo.get("html_url", f"https://github.com/{USERNAME}/{name}")

        rows.append(
            f"| [{name}]({url}) | {description} | {language} | {commits_display} "
            f"| {visibility} | {last_updated} |"
        )

    repo_table = (
        "| Repository | Description | Language | Commits | Visibility | Last Updated |\n"
        "|---|---|---|---:|---|---|\n" + "\n".join(rows)
    )

    if not using_pat and private_count == 0:
        repo_summary = (
            f"**{public_count} public repositories** "
            f"_(private repo count unavailable without an authenticated token — "
            f"add a `PROFILE_GH_TOKEN` secret to include it)_"
        )
    else:
        repo_summary = (
            f"**{total_count} total repositories** — "
            f"{public_count} public · {private_count} private"
        )

    with open(README, "r", encoding="utf-8") as f:
        readme = f.read()

    readme = replace_inline(
        readme, "<!-- START_REPO_SUMMARY -->", "<!-- END_REPO_SUMMARY -->", repo_summary
    )
    readme = replace_between(
        readme, "<!-- START_REPO_TABLE -->", "<!-- END_REPO_TABLE -->", repo_table
    )

    with open(README, "w", encoding="utf-8") as f:
        f.write(readme)

    print("Repo stats updated successfully.")
    print(f"Total: {total_count}, Public: {public_count}, Private: {private_count}")
    print(f"Using authenticated PAT: {using_pat}")


if __name__ == "__main__":
    main()
