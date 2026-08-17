"""
Renders README.md from two source files:
  - data/profile.json           (all editable content: bio, links, experience, projects...)
  - templates/README.template.md (fixed layout with {{PLACEHOLDER}} tokens)

Run this FIRST in the workflow, before update_solving_stats.py and
update_repo_stats.py — those two scripts fill in the <!-- START_... -->
marker blocks (problem counts, repo stats) that this script leaves at
their default/zero state. Since generate_readme.py fully rewrites
README.md from the template on every run, it must not touch those
marker blocks itself, or the stat scripts would have nothing to update.

To change your bio, links, experience, or projects: edit data/profile.json.
To change layout/structure: edit templates/README.template.md.
Do not hand-edit README.md directly — it gets overwritten on the next run.
"""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "profile.json")
TEMPLATE_PATH = os.path.join(ROOT, "templates", "README.template.md")
README_PATH = os.path.join(ROOT, "README.md")


def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_summary_highlights(data):
    links = data["links"]
    lines = []
    for item in data["summary_highlights"]:
        # Highlight strings may reference {leads_corp}, {linkedin}, etc.
        # using the *keys* of the links dict as format fields.
        lines.append("- " + item.format(**links))
    return "\n".join(lines)


def build_experience_table(data):
    rows = []
    for job in data["experience"]:
        bullets = "<br>".join(f"• {b}" for b in job["bullets"])
        role_org = f"**{job['role']}**<br><sub>{job['org']}</sub>"
        rows.append(f"| {role_org} | **{job['period']}** | {bullets} |")
    return "\n".join(rows)


def build_projects_table(data):
    rows = []
    for p in data["projects"]:
        stack = "<br>".join(f"`{s}`" for s in p["stack"])
        highlights = "<br>".join(f"• {h}" for h in p["highlights"])
        links = f"[Code]({p['repo_url']})"
        if p.get("live_url"):
            links += f" · [Live]({p['live_url']})"
        rows.append(f"| **{p['name']}** | {stack} | {highlights} | {links} |")
    return "\n".join(rows)


def build_education(data):
    blocks = []
    for e in data["education"]:
        blocks.append(
            f"- **{e['degree']}**\n"
            f"  - **Institution:** [{e['institution']}]({e['institution_url']}), {e['location']}\n"
            f"  - {e['detail']}\n"
            f"  - **Duration:** {e['period']}"
        )
    return "\n\n".join(blocks)


def build_certifications(data):
    return "\n".join(f"  - [**{c['name'].split(' — ')[0]}** — {c['name'].split(' — ')[1]}]({c['url']})"
                      if " — " in c["name"] else f"  - [{c['name']}]({c['url']})"
                      for c in data["certifications"])


def build_leadership(data):
    lines = []
    for l in data["leadership"]:
        lines.append(f"  - **[{l['role']}]({l['role_url']})** ({l['period']}): {l['detail']}")
    return "\n".join(lines)


def render(data):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    links = data["links"]

    replacements = {
        "{{NAME}}": data["name"],
        "{{TITLE}}": data["title"],
        "{{AVATAR_URL}}": data["avatar_url"],
        "{{TAGLINE}}": data["tagline"],
        "{{SUMMARY}}": data["summary"],
        "{{NARRATIVE}}": data["narrative"],
        "{{SUMMARY_HIGHLIGHTS}}": build_summary_highlights(data),
        "{{EXPERIENCE_TABLE}}": build_experience_table(data),
        "{{PROJECTS_TABLE}}": build_projects_table(data),
        "{{EDUCATION}}": build_education(data),
        "{{CERTIFICATIONS}}": build_certifications(data),
        "{{LEADERSHIP}}": build_leadership(data),
        "{{OPEN_TO}}": data["open_to"],
        "{{EMAIL_BADGE}}": links["email"].replace("@", "%40"),
    }

    # Every top-level links.* entry becomes {{LINK_KEY}} (upper-cased).
    for key, value in links.items():
        replacements[f"{{{{LINK_{key.upper()}}}}}"] = value

    for token, value in replacements.items():
        template = template.replace(token, value)

    leftover = re.findall(r"{{[A-Z_]+}}", template)
    if leftover:
        raise ValueError(f"Unfilled placeholders left in README: {sorted(set(leftover))}")

    return template


def main():
    data = load_data()
    rendered = render(data)
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(rendered)
    print("README.md generated from data/profile.json.")


if __name__ == "__main__":
    main()
