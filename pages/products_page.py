from playwright.sync_api import Locator, Page, expect


class ProductsPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self):
        self.page.goto("/inventory.html")

    def items(self) -> Locator:
        return self.page.get_by_test_id("inventory-item")

    def product_card(self, name: str) -> Locator:
        return self.items().filter(has_text=name)

    def button_for(self, name: str) -> Locator:
        return self.product_card(name).locator("button")

    def cart_badge(self) -> Locator:
        return self.page.get_by_test_id("shopping-cart-badge")

    def add_to_cart(self, name: str):
        button = self.button_for(name)
        expect(button).to_have_text("Add to cart")
        button.click()
        expect(button).to_have_text("Remove")

    def remove_from_cart(self, name: str):
        button = self.button_for(name)
        expect(button).to_have_text("Remove")
        button.click()
        expect(button).to_have_text("Add to cart")

    def try_add_to_cart(self, name: str) -> bool:
        button = self.button_for(name)
        if not button.is_visible():
            return False
        button.click()
        return True
