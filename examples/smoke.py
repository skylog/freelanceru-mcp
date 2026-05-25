import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freelanceru_api import FreelanceRuClient


async def main():
    client = FreelanceRuClient()
    try:
        projects = await client.projects(require_login=False, per_page=5)
        print(f"projects={len(projects)}")
        if projects:
            print(projects[0]["title"])
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
