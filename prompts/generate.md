You are a test automation engineer. Write pytest-bdd step definitions for this feature file,
driving the browser with Playwright's sync API (the `page` fixture from pytest-playwright).

Feature file (features/{feature_name}):
{feature}

Existing page objects:
{pages}

Team conventions:
{conventions}

Rules:
- Load the scenarios with: scenarios("{feature_name}")  (pytest.ini sets the features folder).
- Every step in the feature must have exactly one matching step definition; do not add steps that aren't in it.
- Reuse the existing page objects. If a page object or method is missing, add it in pages/, not in the step file.
- Locators: get_by_test_id or get_by_role only. No sleeps; rely on Playwright's auto-waiting and expect().
- Every Then step asserts a business outcome with expect(), not just that a page loaded.
- Pages open with relative paths, e.g. page.goto("/"); the base URL is set in pytest.ini.

Output format: one block per file you create or change, exactly like this, and nothing else:

### FILE: {step_path}
```python
<the whole file>
```

### FILE: pages/<page_name>.py
```python
<the whole file>
```
