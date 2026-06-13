# P2.1 Simulated Soak Report

- Phase: `P2.1`
- Work package: `WP-06`
- Status: `PASS`
- Simulated soak: `PASS`
- Live soak: `NOT_RUN`
- Timestamp UTC: `2026-06-13T14:39:53Z`
- Commit baseline: `80ebe318b5e89e9b2b56a4ad2ccaf21b2c833906`

## Command

`python -c "from engine.tests.unit.test_market_data_reliability import run_simulated_24h_soak; ..."`

## Metrics

| Metric | Value |
| ------ | ----- |
| Simulated runtime cycles | `48` |
| Simulated timeframe count | `4` |
| Heartbeats recorded | `48` |
| Cursor rows | `5` |
| Latest tick rows | `1` |
| Latest bar rows | `8` |
| Total ticks collected | `144` |
| Recovery events | `8` |
| Error count | `0` |
| Duplicate incidents | `0` |
| Parquet file count | `162` |
| SQLite size bytes | `77824` |
| Peak memory bytes | `538870` |
| Max loop latency ms | `49.85540000052424` |
| Max write latency ms | `33.9142999946489` |

## Notes

- The soak run is a deterministic fake-backend simulation covering 24 hours of runtime-equivalent collection with reconnect events, storage writes, heartbeat recording, and multiple timeframe transitions.
- Live soak remains `NOT_RUN` because live MT5 is still blocked in the current environment.
