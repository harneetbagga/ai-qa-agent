import re

from playwright.sync_api import expect
from pytest_bdd import given, parsers, scenarios, then, when

from pages.cart_page import CartPage
from pages.login_page import LoginPage
from pages.products_page import ProductsPage

scenarios("add_to_cart.feature")


# ---------- Background ----------

@given(parsers.parse('I am logged in as "{username}"'))
def logged_in_as(page, username):
    LoginPage(page).log_in(username)


@given("I am on the Products page")
def on_products_page(page):
    products = ProductsPage(page)
    products.goto()
    expect(page).to_have_url(re.compile(r"/inventory\.html$"))
    expect(products.items().first).to_be_visible()


# ---------- Adding / removing ----------

@when(parsers.parse('I add "{product}" to the cart'))
def add_product(page, product):
    ProductsPage(page).add_to_cart(product)


@given(parsers.parse('I have added "{product}" to the cart'))
def have_added_product(page, product):
    ProductsPage(page).add_to_cart(product)


@given(parsers.parse('I remove "{product}" from the cart'))
@when(parsers.parse('I remove "{product}" from the cart'))
def remove_product(page, product):
    ProductsPage(page).remove_from_cart(product)


@when(parsers.parse('I attempt to add "{product}" to the cart'))
def attempt_add_product(page, product):
    ProductsPage(page).try_add_to_cart(product)


# ---------- Cart state ----------

@then(parsers.parse('"{product}" is in my cart'))
def product_in_cart(page, product):
    cart = CartPage(page)
    cart.goto()
    expect(cart.item(product)).to_have_count(1)


@then(parsers.parse('"{product}" is not in my cart'))
def product_not_in_cart(page, product):
    cart = CartPage(page)
    cart.goto()
    expect(cart.item(product)).to_have_count(0)


@given("my cart has no items")
def cart_has_no_items(page):
    cart = CartPage(page)
    cart.goto()
    expect(cart.items()).to_have_count(0)


@when("I view my cart")
def view_cart(page):
    CartPage(page).goto()


@then(parsers.parse('my cart lists "{product}" priced at "{price}"'))
def cart_lists_product(page, product, price):
    cart = CartPage(page)
    expect(cart.item(product)).to_have_count(1)
    expect(cart.price_of(product)).to_have_text(price)


@then(parsers.parse('my cart does not list "{product}"'))
def cart_does_not_list_product(page, product):
    expect(CartPage(page).item(product)).to_have_count(0)


# ---------- Badge ----------

@then(parsers.parse('the cart badge shows "{count}"'))
def cart_badge_shows(page, count):
    expect(ProductsPage(page).cart_badge()).to_have_text(count)


@then("no cart badge is shown")
def no_cart_badge(page):
    expect(ProductsPage(page).cart_badge()).to_have_count(0)


# ---------- Button state ----------

@then(parsers.parse('the button for "{product}" reads "{label}"'))
def button_reads(page, product, label):
    expect(ProductsPage(page).button_for(product)).to_have_text(label)


# ---------- Logged-out shopper ----------

@given("I am not logged in")
def not_logged_in(page):
    # The Background has already logged in and loaded the Products page.
    # Drop the session, then request a protected page so the app sends the
    # shopper back to the login page with its access error.
    page.context.clear_cookies()
    ProductsPage(page).goto()


@then(parsers.parse('I am sent to the login page with the error "{message}"'))
@then(parsers.parse('I am shown "{message}"'))
def logged_out_shown_message(page, message):
    # A logged-out shopper is redirected to the login page, which shows the error.
    expect(page).to_have_url(re.compile(r"saucedemo\.com/?$"))
    expect(page.get_by_test_id("error")).to_have_text(message)
