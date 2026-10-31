from playwright.sync_api import Page

DEFAULT_PASSWORD = "secret_sauce"


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self):
        self.page.goto("/")

    def log_in(self, username: str, password: str = DEFAULT_PASSWORD):
        self.goto()
        self.page.get_by_test_id("username").fill(username)
        self.page.get_by_test_id("password").fill(password)
        self.page.get_by_test_id("login-button").click()
