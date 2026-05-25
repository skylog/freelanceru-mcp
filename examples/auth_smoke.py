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
        projects = await client.projects(require_login=True, per_page=5)
        print(f"auth_projects={len(projects)}")
        if projects:
            print(projects[0]["title"])
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
