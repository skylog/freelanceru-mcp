from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from freelanceru_api import FreelanceRuClient

load_dotenv()

mcp = FastMCP("freelanceru-mcp")


async def with_client(fn):
    client = FreelanceRuClient()
    try:
        return await fn(client)
    finally:
        await client.close()


@mcp.tool()
async def freelanceru_session() -> dict[str, Any]:
    """Check whether Freelance.ru credentials can authenticate."""

    async def run(client: FreelanceRuClient):
        await client.ensure_login()
        return await client.session()

    return await with_client(run)


@mcp.tool()
async def freelanceru_projects(
    query: str = "",
    page: int = 1,
    per_page: int = 25,
    require_login: bool = True,
) -> list[dict[str, Any]]:
    """List Freelance.ru projects from the project search feed."""

    async def run(client: FreelanceRuClient):
        return await client.projects(
            query=query or None,
            page=max(1, page),
            per_page=max(1, min(per_page, 50)),
            require_login=require_login,
        )

    return await with_client(run)


@mcp.tool()
async def freelanceru_project(project_id_or_url: str, require_login: bool = True) -> dict[str, Any]:
    """Fetch a Freelance.ru project detail page by URL or project id."""

    async def run(client: FreelanceRuClient):
        return await client.project(project_id_or_url, require_login=require_login)

    return await with_client(run)


@mcp.tool()
async def freelanceru_captcha_required() -> dict[str, bool]:
    """Return whether Freelance.ru login currently asks this session for captcha."""

    async def run(client: FreelanceRuClient):
        return {"captcha_required": await client.captcha_required()}

    return await with_client(run)


if __name__ == "__main__":
    mcp.run()
