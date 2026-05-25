# freelanceru-mcp

MCP server for Freelance.ru: search real projects, inspect protected account
pages, read notifications, prepare proposals, and expose the data to Claude,
Codex, Cursor, or any other MCP client.

Freelance.ru does not provide a documented public API for this workflow. This
server logs in through `id.freelance.ru`, uses the same project search filters as
the website, and parses the HTML pages that freelancers normally use in the
browser.

## What You Can Do

- Search projects from `https://freelance.ru/project/search/pro`.
- Use real filters: keywords, stop words, categories, budget range, payment type,
  premium/open access flags, pagination.
- Open project detail pages and detect whether the current account has access.
- Read account sections such as profile, applications, bookmarks, offers,
  partners, contests, marketplace, and finance.
- Read notifications and notification folders.
- Inspect proposal forms before sending anything.
- Prepare proposal payloads in dry-run mode by default.
- Optionally submit a proposal with an explicit `dry_run=false`.
- Check whether login currently requires captcha.

## Tools

| Tool | Purpose |
| --- | --- |
| `freelanceru_session` | Log in and return current session status |
| `freelanceru_projects` | Search projects with Freelance.ru search filters |
| `freelanceru_project` | Fetch one project detail page by URL or project id |
| `freelanceru_notifications` | Read notifications or a notification folder |
| `freelanceru_page` | Read protected account pages |
| `freelanceru_offer_form` | Inspect a proposal form without submitting |
| `freelanceru_submit_offer` | Prepare or submit a proposal; dry-run is default |
| `freelanceru_talk_me` | Read talk.freelance.ru profile if the session supports it |
| `freelanceru_talk_chats` | Read talk.freelance.ru chats if the session supports it |
| `freelanceru_categories` | Return category ids, payment ids, and account sections |
| `freelanceru_captcha_required` | Check whether direct login currently requires captcha |

## Quick Start

```bash
git clone https://github.com/skylog/freelanceru-mcp.git
cd freelanceru-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell:

```powershell
git clone https://github.com/skylog/freelanceru-mcp.git
cd freelanceru-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env`:

```env
FREELANCE_RU_LOGIN=your_login_or_email
FREELANCE_RU_PASSWORD=your_password
```

Run:

```bash
python server.py
```

The server speaks MCP over stdio.

## MCP Config

Unix-like systems:

```json
{
  "mcpServers": {
    "freelanceru": {
      "command": "/path/to/freelanceru-mcp/.venv/bin/python",
      "args": ["/path/to/freelanceru-mcp/server.py"]
    }
  }
}
```

Windows:

```json
{
  "mcpServers": {
    "freelanceru": {
      "command": "C:\\Projects\\freelanceru-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Projects\\freelanceru-mcp\\server.py"]
    }
  }
}
```

## Search Examples

Search Python and web projects:

```text
freelanceru_projects(
  query="python, парсер",
  match_mode="or",
  categories=["it", "web"],
  min_budget=5000,
  include_without_budget=false,
  payment_types=["safe_deal"],
  page=1,
  per_page=25
)
```

Find text-writing jobs without a fixed budget:

```text
freelanceru_projects(
  query="seo, карточки товаров",
  categories=["texts", "marketing"],
  include_open_for_all=true,
  include_premium=false,
  include_without_budget=true
)
```

## Search Filters

`freelanceru_projects` maps to the website form on
`https://freelance.ru/project/search/pro`.

| Argument | Site parameter | Meaning |
| --- | --- | --- |
| `query` | `q` | Keywords, comma-separated |
| `exclude` | `e` | Stop words, comma-separated |
| `match_mode` | `m` | `or` for any keyword, `and` for all keywords |
| `categories` | `c[]` | Category aliases, names, or ids |
| `min_budget` | `f` | Minimum budget |
| `max_budget` | `t` | Maximum budget |
| `include_open_for_all` | `a` | Include projects open to everyone |
| `include_premium` | `v` | Include premium-access projects |
| `include_without_budget` | `o` | Include projects without stated budget |
| `payment_types` | `b[]` | `agreement`, `safe_deal`, `contract`, or ids `1`, `2`, `3` |
| `page` | `page` | Page number |
| `per_page` | `per-page` | Items per page, capped at 50 |

Common category aliases:

| Alias | Category |
| --- | --- |
| `web` | Веб-разработка и Продуктовый дизайн |
| `it` | ИТ и Разработка |
| `ai` | Искусственный интеллект |
| `texts` | Тексты |
| `marketing` | Маркетинг и Реклама |
| `seo` | Интернет продвижение |
| `engineering` | Инженерия |
| `graphic_design` | Графический дизайн |
| `translation` | Переводы |
| `photo` | Фотография |

Use `freelanceru_categories` to get the full category and payment list.

## Account Pages

`freelanceru_page(section=...)` supports:

| Section | Page |
| --- | --- |
| `profile` | `/profile/personal` |
| `my_applications` | `/setup/?cmd=myprojects#my_proj_req` |
| `bookmarks` | `/setup/?cmd=bookmarks` |
| `offers` | `/offer/my` |
| `partners` | `/partners/my` |
| `market` | `/market/my` |
| `contests` | `/tender/contest/my` |
| `finance` | `/profile/finance` |

Notifications:

```text
freelanceru_notifications()
freelanceru_notifications(folder_id="15")
```

## Proposal Flow

Open a project:

```text
freelanceru_project("https://freelance.ru/projects/example-1668535.html")
```

If the account can respond, the result includes `offer_url`. Inspect the form:

```text
freelanceru_offer_form("1668535")
```

Prepare a proposal without publishing:

```text
freelanceru_submit_offer(
  project_id_or_url="1668535",
  message="Здравствуйте. Готов выполнить задачу.",
  cost=1600,
  term=20,
  question="Можно уточнить объем работ?",
  dry_run=true
)
```

Publish only with an explicit opt-in:

```text
freelanceru_submit_offer(
  project_id_or_url="1668535",
  message="Здравствуйте. Готов выполнить задачу.",
  cost=1600,
  term=20,
  dry_run=false
)
```

`dry_run=true` is the default to reduce the chance of accidentally posting an
offer from an automated agent.

## Development Checks

```bash
python -m compileall .
python examples/smoke.py
python examples/auth_smoke.py
```

`examples/auth_smoke.py` requires `FREELANCE_RU_LOGIN` and
`FREELANCE_RU_PASSWORD`.

## Security

- Keep credentials in local environment variables or `.env`.
- Do not commit `.env`, cookies, browser profiles, or logs containing secrets.
- Rotate credentials if they were pasted into an issue, prompt, shell history, or
  public repository.
- `freelanceru_submit_offer` can publish a real marketplace response when
  `dry_run=false`; review the payload first.

## Limitations

- Captcha can block direct login. Use `freelanceru_captcha_required` to diagnose
  that state.
- `talk.freelance.ru` uses an additional OAuth flow. The server attempts it
  automatically, but the chat API surface is currently limited to account info
  and chat list discovery.
- HTML parsing can break if Freelance.ru changes its markup.
- This project is not affiliated with Freelance.ru.

## License

MIT
