from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://freelance.ru"
ID_BASE_URL = "https://id.freelance.ru"
LOGIN_URL = f"{ID_BASE_URL}/api/auth/login"
SESSION_URL = f"{ID_BASE_URL}/api/auth/session"
CAPTCHA_REQUIRED_URL = f"{ID_BASE_URL}/api/auth/login/captcha-required"
PROJECTS_URL = f"{BASE_URL}/project/search/pro"
TALK_BASE_URL = "https://talk.freelance.ru"
PROTECTED_PAGES = {
    "profile": "/profile/personal",
    "my_applications": "/setup/?cmd=myprojects#my_proj_req",
    "bookmarks": "/setup/?cmd=bookmarks",
    "offers": "/offer/my",
    "partners": "/partners/my",
    "market": "/market/my",
    "contests": "/tender/contest/my",
    "finance": "/profile/finance",
}

CATEGORIES = {
    "3d": {"id": "577", "name": "3D графика"},
    "art": {"id": "590", "name": "Арт и Иллюстрации"},
    "consulting": {"id": "133", "name": "Аутсорсинг и Консалтинг"},
    "web": {"id": "116", "name": "Веб-разработка и Продуктовый дизайн"},
    "graphic_design": {"id": "40", "name": "Графический дизайн"},
    "space_design": {"id": "716", "name": "Дизайн пространства"},
    "engineering": {"id": "186", "name": "Инженерия"},
    "seo": {"id": "673", "name": "Интернет продвижение"},
    "ai": {"id": "724", "name": "Искусственный интеллект"},
    "it": {"id": "4", "name": "ИТ и Разработка"},
    "marketing": {"id": "117", "name": "Маркетинг и Реклама"},
    "motion": {"id": "565", "name": "Медиа и Моушен дизайн"},
    "music": {"id": "89", "name": "Музыка и Звук"},
    "education": {"id": "663", "name": "Обучение и Образование"},
    "translation": {"id": "29", "name": "Переводы"},
    "texts": {"id": "124", "name": "Тексты"},
    "photo": {"id": "98", "name": "Фотография"},
}

PAYMENT_TYPES = {
    "agreement": "1",
    "safe_deal": "2",
    "contract": "3",
}


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

        await self.establish_main_session()
        self._logged_in = True
        return True

    async def establish_main_session(self, return_url: str = "/profile/personal") -> None:
        response = await self.http.get(
            f"{BASE_URL}/auth/login",
            params={"return_url": return_url},
            follow_redirects=False,
        )
        location = response.headers.get("location", "")
        if not location.startswith(ID_BASE_URL):
            await self.http.get(f"{BASE_URL}/profile/after-login")
            return
        query = dict(parse_qsl(urlparse(location).query))
        if not query.get("client_id") or not query.get("redirect_uri"):
            raise FreelanceRuError("main site OAuth redirect is missing required parameters")
        check = await self.http.get(
            f"{ID_BASE_URL}/api/authorize/check",
            params={"client_id": query["client_id"], "redirect_uri": query["redirect_uri"]},
        )
        check.raise_for_status()
        authorize = await self.http.post(f"{ID_BASE_URL}/api/authorize", json={}, params=query)
        authorize.raise_for_status()
        data = authorize.json()
        if not data.get("code"):
            raise FreelanceRuError("main site OAuth authorization did not return a code")
        callback_params = {"code": data["code"], "state": query.get("state", "")}
        if data.get("scope"):
            callback_params["scope"] = data["scope"]
        callback_url = f"{query['redirect_uri']}?{urlencode(callback_params)}"
        await self.http.get(callback_url)

    async def establish_talk_session(self) -> None:
        response = await self.http.get(f"{TALK_BASE_URL}/api/auth/login", follow_redirects=False)
        location = response.headers.get("location", "")
        if not location.startswith(ID_BASE_URL):
            return
        query = dict(parse_qsl(urlparse(location).query))
        authorize = await self.http.post(f"{ID_BASE_URL}/api/authorize", json={}, params=query)
        authorize.raise_for_status()
        data = authorize.json()
        if not data.get("code"):
            raise FreelanceRuError("talk OAuth authorization did not return a code")
        callback_params = {"code": data["code"], "state": query.get("state", "")}
        if data.get("scope"):
            callback_params["scope"] = data["scope"]
        callback_url = f"{query['redirect_uri']}?{urlencode(callback_params)}"
        await self.http.get(callback_url)

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
        exclude: str | None = None,
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
        if require_login:
            await self.ensure_login()
        params = build_search_params(
            query=query,
            exclude=exclude,
            match_mode=match_mode,
            categories=categories,
            min_budget=min_budget,
            max_budget=max_budget,
            include_open_for_all=include_open_for_all,
            include_premium=include_premium,
            include_without_budget=include_without_budget,
            payment_types=payment_types,
            page=page,
            per_page=per_page,
        )
        response = await self.http.get(PROJECTS_URL, params=params)
        response.raise_for_status()
        return [asdict(project) for project in parse_projects(response.text)]

    async def project(self, project_id_or_url: str, require_login: bool = True) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        url = normalize_project_url(project_id_or_url)
        response = await self.http.get(url)
        response.raise_for_status()
        return parse_project_detail(response.text, str(response.url))

    async def notifications(
        self,
        folder_id: str | int | None = None,
        require_login: bool = True,
    ) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        path = "/notification" if folder_id is None else f"/notification/folder/{folder_id}"
        response = await self.http.get(urljoin(BASE_URL, path))
        response.raise_for_status()
        return parse_notifications(response.text, str(response.url))

    async def page_section(self, section: str, require_login: bool = True) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        if section not in PROTECTED_PAGES:
            raise FreelanceRuError(f"unknown section: {section}")
        response = await self.http.get(urljoin(BASE_URL, PROTECTED_PAGES[section]))
        response.raise_for_status()
        return parse_page_summary(response.text, str(response.url), section=section)

    async def offer_form(self, project_id_or_url: str, require_login: bool = True) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        project_id = extract_project_id(project_id_or_url)
        if not project_id:
            detail = await self.project(project_id_or_url, require_login=False)
            project_id = detail.get("id")
        response = await self.http.get(f"{BASE_URL}/project/discussion/start/{project_id}")
        response.raise_for_status()
        return parse_offer_form(response.text, str(response.url), project_id=str(project_id), redact=True)

    async def submit_offer(
        self,
        project_id_or_url: str,
        message: str,
        cost: int | None = None,
        term: int | None = None,
        question: str = "",
        signature: bool = True,
        dry_run: bool = True,
        require_login: bool = True,
    ) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        project_id = extract_project_id(project_id_or_url)
        if not project_id:
            detail = await self.project(project_id_or_url, require_login=False)
            project_id = detail.get("id")
        response = await self.http.get(f"{BASE_URL}/project/discussion/start/{project_id}")
        response.raise_for_status()
        form = parse_offer_form(response.text, str(response.url), project_id=str(project_id), redact=False)
        if form.get("access_denied") or not form.get("can_submit"):
            return {"submitted": False, "dry_run": dry_run, "form": form}
        data = dict(form.get("fields", {}))
        data["StartDiscussionForm[message]"] = message
        data["StartDiscussionForm[question]"] = question
        data["StartDiscussionForm[signature]"] = "1" if signature else "0"
        if cost is not None:
            data["StartDiscussionForm[cost]"] = str(cost)
        if term is not None:
            data["StartDiscussionForm[term]"] = str(term)
        if dry_run:
            return {"submitted": False, "dry_run": True, "action": form.get("action"), "payload": redact_csrf(data), "form": form}
        response = await self.http.post(str(form["action"]), data=data, headers={"Referer": str(form["url"])})
        response.raise_for_status()
        return parse_submit_result(response.text, str(response.url))

    async def talk_me(self, require_login: bool = True) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        response = await self.http.get(f"{TALK_BASE_URL}/api/me")
        if response.status_code == 401:
            await self.establish_talk_session()
            response = await self.http.get(f"{TALK_BASE_URL}/api/me")
        if response.status_code == 401:
            return {"authenticated": False, "note": "talk.freelance.ru OAuth failed"}
        response.raise_for_status()
        return {"authenticated": True, "me": response.json()}

    async def talk_chats(self, offset: int = 0, require_login: bool = True) -> dict[str, Any]:
        if require_login:
            await self.ensure_login()
        response = await self.http.get(f"{TALK_BASE_URL}/api/chats", params={"offset": max(0, offset)})
        if response.status_code == 401:
            await self.establish_talk_session()
            response = await self.http.get(f"{TALK_BASE_URL}/api/chats", params={"offset": max(0, offset)})
        if response.status_code == 401:
            return {"authenticated": False, "items": [], "note": "talk.freelance.ru OAuth failed"}
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"items": data}


def normalize_project_url(project_id_or_url: str) -> str:
    value = str(project_id_or_url).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/"):
        return urljoin(BASE_URL, value)
    if value.isdigit():
        return f"{BASE_URL}/projects/{value}.html"
    return urljoin(BASE_URL, value)


def build_search_params(
    query: str | None = None,
    exclude: str | None = None,
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
) -> list[tuple[str, Any]]:
    params: list[tuple[str, Any]] = [
        ("page", max(1, page)),
        ("per-page", max(1, min(per_page, 50))),
    ]
    if query:
        params.append(("q", query))
        params.append(("m", "and" if match_mode == "and" else "or"))
    if exclude:
        params.append(("e", exclude))
    for category in resolve_categories(categories or []):
        params.append(("c[]", category))
    if min_budget is not None:
        params.append(("f", max(0, int(min_budget))))
    if max_budget is not None:
        params.append(("t", max(0, int(max_budget))))
    params.append(("a", "1" if include_open_for_all else "0"))
    params.append(("v", "1" if include_premium else "0"))
    params.append(("o", "1" if include_without_budget else "0"))
    for payment_type in resolve_payment_types(payment_types or []):
        params.append(("b[]", payment_type))
    return params


def resolve_categories(categories: list[str]) -> list[str]:
    resolved = []
    lower_name_map = {v["name"].lower(): v["id"] for v in CATEGORIES.values()}
    for item in categories:
        value = str(item).strip()
        if not value:
            continue
        if value in {v["id"] for v in CATEGORIES.values()}:
            resolved.append(value)
            continue
        if value in CATEGORIES:
            resolved.append(CATEGORIES[value]["id"])
            continue
        by_name = lower_name_map.get(value.lower())
        if by_name:
            resolved.append(by_name)
    return list(dict.fromkeys(resolved))


def resolve_payment_types(payment_types: list[str]) -> list[str]:
    resolved = []
    for item in payment_types:
        value = str(item).strip()
        if not value:
            continue
        resolved.append(PAYMENT_TYPES.get(value, value))
    return [v for v in dict.fromkeys(resolved) if v in set(PAYMENT_TYPES.values())]


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
    offer_link = soup.select_one('a[href^="/project/discussion/start/"]')
    access_denied = "Доступ к этому заданию" in text or "Dostup k etomu zadaniyu" in text
    return {
        "id": project_id_from_url(url),
        "url": url,
        "title": title,
        "budget": budget,
        "currency": "RUB",
        "access_denied": access_denied,
        "offer_url": urljoin(BASE_URL, offer_link.get("href")) if offer_link else None,
        "text": text[:8000],
    }


def parse_notifications(page: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(page, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    folders = []
    for link in soup.select('a[href^="/notification/folder/"]'):
        href = link.get("href", "")
        folder_id = href.rstrip("/").split("/")[-1]
        folders.append({"id": folder_id, "title": clean_text(link.get_text(" ", strip=True)), "url": urljoin(BASE_URL, href)})
    items = []
    for link in soup.select('a[href]'):
        href = link.get("href", "")
        label = clean_text(link.get_text(" ", strip=True))
        if label and "/notification" not in href and len(label) > 8:
            items.append({"title": label[:300], "url": urljoin(BASE_URL, href)})
    return {"url": url, "empty": "Уведомлений нет" in text, "folders": unique_items(folders), "items": unique_items(items)[:50], "text": text[:4000]}


def parse_page_summary(page: str, url: str, section: str) -> dict[str, Any]:
    soup = BeautifulSoup(page, "html.parser")
    title_node = soup.find("h1") or soup.find("h2")
    title = clean_text(title_node.get_text(" ", strip=True) if title_node else soup.title.string if soup.title else "")
    text = clean_text(soup.get_text(" ", strip=True))
    links = []
    for link in soup.select("a[href]"):
        label = clean_text(link.get_text(" ", strip=True))
        if label:
            links.append({"title": label[:160], "url": urljoin(BASE_URL, link.get("href", ""))})
    return {"section": section, "url": url, "title": title, "links": unique_items(links)[:80], "text": text[:8000]}


def parse_offer_form(page: str, url: str, project_id: str, redact: bool = True) -> dict[str, Any]:
    soup = BeautifulSoup(page, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    form = soup.find("form")
    fields: dict[str, str] = {}
    if form:
        for field in form.find_all(["input", "textarea", "select"]):
            name = field.get("name")
            if not name:
                continue
            if field.name == "textarea":
                value = field.get_text()
            else:
                value = field.get("value", "")
            if field.get("type") == "checkbox" and not field.has_attr("checked"):
                continue
            fields[name] = value
    output_fields = redact_csrf(fields) if redact else fields
    return {
        "project_id": project_id,
        "url": url,
        "action": urljoin(BASE_URL, form.get("action", "")) if form else None,
        "method": (form.get("method", "get").lower() if form else None),
        "can_submit": bool(form and soup.select_one('button[type="submit"], input[type="submit"]')),
        "access_denied": "Доступ к этому заданию" in text,
        "daily_remaining": parse_daily_remaining(text),
        "fields": output_fields,
        "required_payload_keys": [
            "StartDiscussionForm[cost]",
            "StartDiscussionForm[term]",
            "StartDiscussionForm[message]",
            "StartDiscussionForm[question]",
            "StartDiscussionForm[signature]",
        ],
        "text": text[:5000],
    }


def parse_submit_result(page: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(page, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    return {"submitted": True, "dry_run": False, "url": url, "text": text[:4000]}


def parse_daily_remaining(text: str) -> int | None:
    match = re.search(r"Осталось\s+(\d+)", text)
    return int(match.group(1)) if match else None


def redact_csrf(data: dict[str, Any]) -> dict[str, Any]:
    return {key: ("<csrf>" if key == "_csrf" and value else value) for key, value in data.items()}


def unique_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        marker = tuple(sorted(item.items()))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def extract_project_id(value: str) -> str | None:
    text = str(value)
    match = re.search(r"(?:-|/)(\d+)(?:\.html|$|[/?#])", text)
    if match:
        return match.group(1)
    if text.strip().isdigit():
        return text.strip()
    return None


def project_id_from_url(url: str) -> str:
    match = re.search(r"-(\d+)\.html(?:$|\?)", url)
    if match:
        return match.group(1)
    match = re.search(r"/(?:no-access|discussion/start)/(\d+)(?:$|[/?#])", url)
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
