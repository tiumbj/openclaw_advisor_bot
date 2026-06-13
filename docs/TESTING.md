# Testing

Version: `1.2.1`  
Phase: `P2.1`

- `engine\tests\unit` covers environment, config, skills, health helpers, and market-data
  reliability logic.
- `engine\tests\integration` covers CLI commands, rendered outputs, and MT5 read-only command
  behavior with fake backend coverage.
- `engine\tests\security` covers forbidden-call, constant-resolution, dynamic-import,
  documentation-only, test-only, and reachable-dependency scans.
- `engine\tests\live` is marked with `@pytest.mark.live` and excluded from default test runs.
