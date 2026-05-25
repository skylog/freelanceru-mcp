# freelanceru-mcp

MCP server for Freelance.ru project search.

It follows the same practical shape as `oxgeneral/kwork-mcp`: a small Python
stdio MCP server, local `.env` credentials, and direct requests to the freelance
marketplace. Freelance.ru does not expose a documented public API for this flow,
so this server uses the `id.freelance.ru` login endpoint and parses the project
search HTML page.

## Tools

| Tool | What it does |
| --- | --- |
| `freelanceru_session` | Checks login/session status |
| `freelanceru_projects` | Lists projects from `https://freelance.ru/project/search/pro` |
| `freelanceru_project` | Fetches one project detail page by URL or id |
| `freelanceru_captcha_required` | Checks whether login currently requires captcha |

## Install

```bash
git clone https://github.com/skylog/freelanceru-mcp.git
cd freelanceru-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell:

```powershell
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

## MCP Config

Claude Desktop / Claude Code:

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

Windows example:

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

## Run

```bash
python server.py
```

The server speaks MCP over stdio.

## Notes

- Credentials stay local in `.env`; `.env` is ignored by git.
- If Freelance.ru asks for captcha, direct login will fail. Use
  `freelanceru_captcha_required` to diagnose that state.
- HTML parsing can break if Freelance.ru changes page markup.
- This project is not affiliated with Freelance.ru.

## License

MIT
