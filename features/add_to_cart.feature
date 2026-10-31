Feature: Add products to the cart

  Background:
    Given I am logged in as "standard_user"
    And I am on the Products page

  @smoke
  Scenario Outline: Adding a product puts it in the cart
    When I add "<product>" to the cart
    Then "<product>" is in my cart

    Examples:
      | product               |
      | Sauce Labs Backpack   |
      | Sauce Labs Bike Light |

  @smoke
  Scenario: Cart badge shows 1 after adding one product
    When I add "Sauce Labs Backpack" to the cart
    Then the cart badge shows "1"

  @regression
  Scenario: Cart badge shows 2 after adding both products
    When I add "Sauce Labs Backpack" to the cart
    And I add "Sauce Labs Bike Light" to the cart
    Then the cart badge shows "2"

  @smoke
  Scenario Outline: Added product's button changes to Remove
    When I add "<product>" to the cart
    Then the button for "<product>" reads "Remove"

    Examples:
      | product               |
      | Sauce Labs Backpack   |
      | Sauce Labs Bike Light |

  @regression
  Scenario Outline: Other products keep the "Add to cart" button when one product is added
    When I add "<added>" to the cart
    Then the button for "<other>" reads "Add to cart"

    Examples:
      | added                 | other                 |
      | Sauce Labs Backpack   | Sauce Labs Bike Light |
      | Sauce Labs Bike Light | Sauce Labs Backpack   |

  @regression
  Scenario: Removing a product takes it out of the cart
    Given I have added "Sauce Labs Backpack" to the cart
    When I remove "Sauce Labs Backpack" from the cart
    Then "Sauce Labs Backpack" is not in my cart

  @regression
  Scenario: Removing a product lowers the cart badge count
    Given I have added "Sauce Labs Backpack" to the cart
    And I have added "Sauce Labs Bike Light" to the cart
    When I remove "Sauce Labs Backpack" from the cart
    Then the cart badge shows "1"

  @regression
  Scenario: Removing a product changes its button back to Add to cart
    Given I have added "Sauce Labs Backpack" to the cart
    When I remove "Sauce Labs Backpack" from the cart
    Then the button for "Sauce Labs Backpack" reads "Add to cart"

  @smoke
  Scenario: No cart badge is shown when the cart is empty
    Given my cart has no items
    Then no cart badge is shown

  @regression
  Scenario: Cart badge disappears when the last item is removed
    Given I have added "Sauce Labs Backpack" to the cart
    When I remove "Sauce Labs Backpack" from the cart
    Then no cart badge is shown

  @regression
  Scenario Outline: Cart page lists an added product with its name and price
    Given I have added "<product>" to the cart
    When I view my cart
    Then my cart lists "<product>" priced at "<price>"

    Examples:
      | product               | price  |
      | Sauce Labs Backpack   | $29.99 |
      | Sauce Labs Bike Light | $9.99  |

  @regression
  Scenario: Cart page lists both added products
    Given I have added "Sauce Labs Backpack" to the cart
    And I have added "Sauce Labs Bike Light" to the cart
    When I view my cart
    Then my cart lists "Sauce Labs Backpack" priced at "$29.99"
    And my cart lists "Sauce Labs Bike Light" priced at "$9.99"

  @regression
  Scenario: Cart page does not list a product after it is removed
    Given I have added "Sauce Labs Bike Light" to the cart
    And I remove "Sauce Labs Bike Light" from the cart
    When I view my cart
    Then my cart does not list "Sauce Labs Bike Light"

  @regression
  Scenario: Shopper who is not logged in cannot add a product to the cart
    Given I am not logged in
    When I attempt to add "Sauce Labs Backpack" to the cart
    Then I am sent to the login page with the error "Epic sadface: You can only access '/inventory.html' when you are logged in."
    And "Sauce Labs Backpack" is not in my cart
