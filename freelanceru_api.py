from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://freelance.ru"
ID_BASE_URL = "https://id.freelance.ru"
LOGIN_URL = f"{ID_BASE_URL}/api/auth/login"
SESSION_URL = f"{ID_BASE_URL}/api/auth/session"
CAPTCHA_REQUIRED_URL = f"{ID_BASE_URL}/api/auth/login/captcha-required"
PROJECTS_URL = f"{BASE_URL}/project/search/pro"


class FreelanceRuError(RuntimeError):
    pass


@dataclass
class Project:
    id: str
    title: str
    url: str
    description: str
    category: str | None
    budget: float | None
    currency: str
    duration_days: int | None
    payment_type: str | None
    customer: str | None
    views: int | None
    responses: int | None
    published_text: str | None


class FreelanceRuClient:
    def __init__(
        self,
        login: str | None = None,
        password: str | None = None,
        timeout: float = 25.0,
    ) -> None:
        self.login_value = login or os.getenv("FREELANCE_RU_LOGIN")
        self.password = password or os.getenv("FREELANCE_RU_PASSWORD")
        self.http = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0 Safari/537.36"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )
        self._logged_in = False

    async def close(self) -> None:
        await self.http.aclose()

    async def login(self) -> bool:
        if not self.login_value or not self.password:
            raise FreelanceRuError("FREELANCE_RU_LOGIN/FREELANCE_RU_PASSWORD are not configured")

        await self.http.get(CAPTCHA_REQUIRED_URL)
        response = await self.http.post(
            LOGIN_URL,
            json={
                "identifier": self.login_value,
                "password": self.password,
                "captcha_token": "",
            },
            headers={
                "Origin": ID_BASE_URL,
                "Referer": f"{ID_BASE_URL}/login?redirect_uri={BASE_URL}/profile/after-login",
            },
        )
        if response.status_code not in (200, 204):
            captcha_required = await self.captcha_required()
            detail = f"HTTP {response.status_code}"
            if captcha_required:
                detail += "; captcha is required"
            raise FreelanceRuError(f"login failed: {detail}")

        await self.http.get(f"{BASE_URL}/profile/after-login")
        self._logged_in = True
        return True

    async def captcha_required(self) -> bool:
        response = await self.http.get(CAPTCHA_REQUIRED_URL)
        if response.status_code != 200:
            return False
        try:
            data = response.json()
        except ValueError:
            return False
        if isinstance(data, bool):
            return data
        if isinstance(data, dict):
            return bool(data.get("required") or data.get("captcha_required"))
        return False

    async def session(self) -> dict[str, Any]:
        response = await self.http.get(SESSION_URL)
        if response.status_code == 401:
            return {"authenticated": False}
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError:
            data = {}
        return {"authenticated": True, "session": data}

    async def ensure_login(self) -> None:
        if self._logged_in:
            return
        current = await self.session()
        if current.get("authenticated"):
            self._logged_in = True
            return
        await self.login()

    async def projects(
        self,
        query: str | None = None,
        page: int = 1,
        per_page: int = 25,
        require_login: bool = True,
    ) -> list[dict[str, Any]]:
        if require_login:
            await self.ensure_login()
        params: dict[str, Any] = {"page": page, "per-page": per_page}
        if query:
            params["q"] = query
        response = await self.http.get(PROJECTS_URL, params=params)
        response.raise_for_status()
        return [asdict(project) for project in parse_projects(response.text)]

    async def project(self, project_id_or_url: str, require_login: bool = True) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        url = normalize_project_url(project_id_or_url)
        response = await self.http.get(url)
        response.raise_for_status()
        return parse_project_detail(response.text, url)


def normalize_project_url(project_id_or_url: str) -> str:
    value = str(project_id_or_url).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/"):
        return urljoin(BASE_URL, value)
    if value.isdigit():
        return f"{BASE_URL}/projects/{value}.html"
    return urljoin(BASE_URL, value)


def parse_projects(page: str) -> list[Project]:
    soup = BeautifulSoup(page, "html.parser")
    projects: list[Project] = []
    seen: set[str] = set()
    for link in soup.select('a[href^="/projects/"][href$=".html"]'):
        url = urljoin(BASE_URL, link.get("href", ""))
        if url in seen:
            continue
        seen.add(url)

        card = find_project_card(link)
        card_text = clean_text(card.get_text(" ", strip=True) if card else "")
        title_node = nearest_title(link)
        title = clean_text(title_node.get_text(" ", strip=True) if title_node else link.get_text(" ", strip=True))
        description = clean_text(link.get_text(" ", strip=True))

        projects.append(
            Project(
                id=project_id_from_url(url),
                title=title,
                url=url,
                description=description,
                category=parse_category(card, title_node),
                budget=parse_budget(card_text),
                currency="RUB",
                duration_days=parse_duration_days(card_text),
                payment_type=parse_payment_type(card_text),
                customer=parse_customer(card_text),
                views=parse_views_responses(card_text)[0],
                responses=parse_views_responses(card_text)[1],
                published_text=parse_publication_text(card_text),
            )
        )
    return projects


def parse_project_detail(page: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(page, "html.parser")
    h1 = soup.find("h1") or soup.find("h2")
    title = clean_text(h1.get_text(" ", strip=True) if h1 else "")
    text = clean_text(soup.get_text(" ", strip=True))
    budget = parse_budget(text)
    return {
        "id": project_id_from_url(url),
        "url": url,
        "title": title,
        "budget": budget,
        "currency": "RUB",
        "text": text[:8000],
    }


def project_id_from_url(url: str) -> str:
    match = re.search(r"-(\d+)\.html(?:$|\?)", url)
    if match:
        return match.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:12]


def nearest_title(link):
    node = link
    for _ in range(5):
        node = node.parent
        if not node:
            break
        title = node.find(["h1", "h2", "h3", "h4"])
        if title:
            return title
    return None


def find_project_card(link):
    node = link
    for _ in range(8):
        node = node.parent
        if not node:
            break
        text = node.get_text(" ", strip=True)
        if "Способ оплаты" in text or "Дата публикации" in text or "Дата последнего изменения" in text:
            return node
    return link.parent


def parse_category(card, title_node) -> str | None:
    if not card or not title_node:
        return None
    for node in title_node.find_all_next(["div", "span", "p"], limit=10):
        text = clean_text(node.get_text(" ", strip=True))
        if text and len(text) < 90 and "Способ оплаты" not in text:
            return text
    return None


def parse_budget(text: str) -> float | None:
    if "Договорная" in text:
        return None
    match = re.search(r"(\d[\d\s]*)\s*(?:Руб|руб|₽)", text)
    return float(match.group(1).replace(" ", "")) if match else None


def parse_duration_days(text: str) -> int | None:
    match = re.search(r"за\s+(\d+)\s+д", text, re.I)
    return int(match.group(1)) if match else None


def parse_payment_type(text: str) -> str | None:
    match = re.search(r"Способ оплаты:\s*([^ЗДО]+)", text)
    return clean_text(match.group(1)) if match else None


def parse_customer(text: str) -> str | None:
    match = re.search(r"Заказчик:\s*(.*?)(?:\s+\d+\s+\d+\s+(?:Обновлено|Опубликовано)|$)", text)
    return clean_text(match.group(1)) if match else None


def parse_views_responses(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"Заказчик:.*?\s(\d{1,5})\s+(\d{1,5})\s+(?:Обновлено|Опубликовано)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_publication_text(text: str) -> str | None:
    match = re.search(r"((?:Обновлено|Опубликовано)\s+.*)$", text)
    return clean_text(match.group(1)) if match else None


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
