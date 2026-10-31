A test failed and was triaged as an APPLICATION bug: {reason}

Write a defect report in Markdown with these headings:
Title, Environment, Steps to reproduce, Expected result, Actual result, Severity (suggested), Evidence.

- Steps come from the scenario, in plain language a developer can follow.
- Expected comes from the scenario; Actual comes from the error. Do not guess beyond them.
- Suggested severity: Critical, High, Medium or Low, with a one-line reason. A person confirms it.

Failing test: {test}
Error: {message}

Details:
{details}

Scenario:
{feature}

Test code:
{test_code}

Page objects:
{pages}
