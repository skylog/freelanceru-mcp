import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freelanceru_api import FreelanceRuClient


async def main():
    client = FreelanceRuClient()
    try:
        print("captcha_required_before=", await client.captcha_required())
        session_before = await client.session()
        print("authenticated_before=", session_before.get("authenticated"))
        await client.ensure_login()
        session_after = await client.session()
        print("authenticated_after=", session_after.get("authenticated"))
        projects = await client.projects(
            require_login=True,
            query="python, сайт",
            categories=["it", "web"],
            min_budget=1000,
            per_page=5,
        )
        print(f"auth_projects={len(projects)}")
        if projects:
            print(projects[0]["title"])
        notifications = await client.notifications()
        print("notifications_empty=", notifications.get("empty"))
        profile = await client.page_section("profile")
        print("profile_title=", profile.get("title"))
        applications = await client.page_section("my_applications")
        print("applications_title=", applications.get("title"))
        offer_form = await client.offer_form("1668535")
        print("offer_can_submit=", offer_form.get("can_submit"))
        dry_run = await client.submit_offer("1668535", "Test dry run only", dry_run=True)
        print("dry_run=", dry_run.get("dry_run"))
        talk_me = await client.talk_me()
        print("talk_authenticated=", talk_me.get("authenticated"))
        talk_chats = await client.talk_chats()
        print("talk_chats=", len(talk_chats.get("items", [])))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
