# Add products to the cart

As a logged-in shopper on saucedemo.com
I want to add products to my cart
So that I can buy them together at checkout

## Acceptance criteria

1. On the Products page, clicking "Add to cart" on a product adds it to the cart.
2. The cart badge in the header shows the number of items in the cart.
3. The product's button changes from "Add to cart" to "Remove".
4. Clicking "Remove" takes the product out of the cart and the badge count goes down.
5. With no items in the cart, no badge is shown.
6. The cart page lists each added product with its name and price.
7. A shopper who is not logged in and opens the Products page is sent back to the login page with the error: "Epic sadface: You can only access ‘/inventory.html’ when you are logged in."
8. 
## Test data

- User: standard_user / secret_sauce
- Products: "Sauce Labs Backpack" ($29.99), "Sauce Labs Bike Light" ($9.99)
