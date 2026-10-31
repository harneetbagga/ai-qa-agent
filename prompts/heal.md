A test failed and was triaged as a TEST bug: {reason}

Propose the smallest change that fixes the test. Rules:
- Never weaken an assertion, delete a check, skip the test, or change an expected value
  so it matches whatever the app happens to show. If that is the only way to make it pass,
  output nothing.
- Change only the broken line(s): usually a locator, a step-matching string or test configuration.
- Base the fix on the page snapshot: use attributes that actually exist in it.
- No sleeps and no wait_for_load_state("networkidle"); use expect(...) assertions, which wait.
- Follow the team conventions.

The same fix should also cover these tests, which failed the same way:
{others}

Page snapshot at failure:
{snapshot}

Failing test: {test}
Error: {message}

Details:
{details}

Test code:
{test_code}

Scenario:
{feature}

Page objects:
{pages}

Team conventions:
{conventions}

Output one block per file you change, with the WHOLE new file, exactly like this:

### FILE: <path, under pages/ or tests/steps/>
```python
<the whole file>
```
