from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from freelanceru_api import CATEGORIES, PAYMENT_TYPES, PROTECTED_PAGES, FreelanceRuClient

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
    exclude: str = "",
    match_mode: str = "or",
    categories: list[str] | None = None,
    min_budget: int | None = None,
    max_budget: int | None = None,
    include_open_for_all: bool = True,
    include_premium: bool = True,
    include_without_budget: bool = True,
    payment_types: list[str] | None = None,
    page: int = 1,
    per_page: int = 25,
    require_login: bool = True,
) -> list[dict[str, Any]]:
    """Search Freelance.ru projects with the same filters as /project/search/pro."""

    async def run(client: FreelanceRuClient):
        return await client.projects(
            query=query or None,
            exclude=exclude or None,
            match_mode=match_mode,
            categories=categories or [],
            min_budget=min_budget,
            max_budget=max_budget,
            include_open_for_all=include_open_for_all,
            include_premium=include_premium,
            include_without_budget=include_without_budget,
            payment_types=payment_types or [],
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
async def freelanceru_notifications(folder_id: str = "", require_login: bool = True) -> dict[str, Any]:
    """Fetch notifications or a notification folder."""

    async def run(client: FreelanceRuClient):
        return await client.notifications(folder_id or None, require_login=require_login)

    return await with_client(run)


@mcp.tool()
async def freelanceru_page(section: str, require_login: bool = True) -> dict[str, Any]:
    """Fetch account pages: profile, my_applications, bookmarks, offers, partners, market, contests, finance."""

    async def run(client: FreelanceRuClient):
        return await client.page_section(section, require_login=require_login)

    return await with_client(run)


@mcp.tool()
async def freelanceru_offer_form(project_id_or_url: str, require_login: bool = True) -> dict[str, Any]:
    """Read the proposal form for a project without submitting anything."""

    async def run(client: FreelanceRuClient):
        return await client.offer_form(project_id_or_url, require_login=require_login)

    return await with_client(run)


@mcp.tool()
async def freelanceru_submit_offer(
    project_id_or_url: str,
    message: str,
    cost: int | None = None,
    term: int | None = None,
    question: str = "",
    signature: bool = True,
    dry_run: bool = True,
    require_login: bool = True,
) -> dict[str, Any]:
    """Prepare or submit a project proposal. dry_run defaults to true and does not publish."""

    async def run(client: FreelanceRuClient):
        return await client.submit_offer(
            project_id_or_url=project_id_or_url,
            message=message,
            cost=cost,
            term=term,
            question=question,
            signature=signature,
            dry_run=dry_run,
            require_login=require_login,
        )

    return await with_client(run)


@mcp.tool()
async def freelanceru_talk_me(require_login: bool = True) -> dict[str, Any]:
    """Read talk.freelance.ru account info when the HTTP session has talk access."""

    async def run(client: FreelanceRuClient):
        return await client.talk_me(require_login=require_login)

    return await with_client(run)


@mcp.tool()
async def freelanceru_talk_chats(offset: int = 0, require_login: bool = True) -> dict[str, Any]:
    """Read talk.freelance.ru chats when the HTTP session has talk access."""

    async def run(client: FreelanceRuClient):
        return await client.talk_chats(offset=offset, require_login=require_login)

    return await with_client(run)


@mcp.tool()
async def freelanceru_categories() -> dict[str, Any]:
    """Return supported Freelance.ru search category and payment filter IDs."""

    return {
        "categories": CATEGORIES,
        "payment_types": PAYMENT_TYPES,
        "account_sections": sorted(PROTECTED_PAGES),
        "search_endpoint": "https://freelance.ru/project/search/pro",
        "query_params": {
            "q": "keywords, comma-separated",
            "e": "excluded words, comma-separated",
            "m": "or|and keyword mode",
            "c[]": "category ids",
            "f": "min budget",
            "t": "max budget",
            "a": "1 include projects open for all",
            "v": "1 include premium access projects",
            "o": "1 include projects without specified budget",
            "b[]": "payment type ids",
            "page": "page number",
            "per-page": "items per page",
        },
    }


@mcp.tool()
async def freelanceru_captcha_required() -> dict[str, bool]:
    """Return whether Freelance.ru login currently asks this session for captcha."""

    async def run(client: FreelanceRuClient):
        return {"captcha_required": await client.captcha_required()}

    return await with_client(run)


if __name__ == "__main__":
    mcp.run()
