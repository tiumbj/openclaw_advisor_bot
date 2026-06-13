# Testing

Version: `1.1.1`  
Phase: `P1.1`

- `engine\tests\unit` covers environment, config, skills, and health helpers.
- `engine\tests\integration` covers CLI commands and rendered outputs.
- `engine\tests\security` covers forbidden-call, constant-resolution, dynamic-import, documentation-only, test-only, and reachable-dependency scans.
- `engine\tests\live` is marked with `@pytest.mark.live` and excluded from default test runs.
