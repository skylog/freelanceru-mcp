from freelanceru_api import parse_project_detail


def test_parse_project_detail_uses_main_content_and_budget():
    html = """
    <html><body>
      <article class="task-card task-card--premium">
        <div class="task-card__main">
          <h1>Разработка tg mini app</h1>
          <div class="task-card__chips">
            <span>Бюджет: 270 000 ₽</span>
            <span>20 откликов</span>
          </div>
          <div class="task-card__description">
            Нужно сделать мини-приложение для Telegram с личным кабинетом и оплатой.
          </div>
        </div>
      </article>
      <footer class="footer">
        Подвал сайта /projects/freelance.ru_2222
      </footer>
    </body></html>
    """

    detail = parse_project_detail(html, "https://freelance.ru/task/view/2222")

    assert detail["title"] == "Разработка tg mini app"
    assert detail["budget"] == 270000
    assert "Подвал сайта" not in detail["text"]
    assert "/projects/freelance.ru_2222" not in detail["text"]
    assert "Нужно сделать мини-приложение" in detail["text"]
