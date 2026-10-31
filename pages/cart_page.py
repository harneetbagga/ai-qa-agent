from playwright.sync_api import Locator, Page


class CartPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self):
        self.page.goto("/cart.html")

    def items(self) -> Locator:
        return self.page.get_by_test_id("inventory-item")

    def item(self, name: str) -> Locator:
        return self.items().filter(has_text=name)

    def price_of(self, name: str) -> Locator:
        return self.item(name).get_by_test_id("inventory-item-price")
