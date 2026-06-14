# P2.2 Provider Configuration Audit

## Supported Providers

- `openai`
- `claude`
- `gemini`
- `deepseek`

## OpenClaw Provider ID Mapping

| User-facing provider | OpenClaw provider id | Enable flag | API key env | Model env | Timeout env |
| -------------------- | -------------------- | ----------- | ----------- | --------- | ----------- |
| `openai` | `openai` | `OPENAI_ENABLED` | `OPENAI_API_KEY` | `OPENAI_MODEL` | `OPENAI_TIMEOUT_SECONDS` |
| `claude` | `anthropic` | `CLAUDE_ENABLED` | `ANTHROPIC_API_KEY` | `CLAUDE_MODEL` | `CLAUDE_TIMEOUT_SECONDS` |
| `gemini` | `google` | `GEMINI_ENABLED` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `GEMINI_MODEL` | `GEMINI_TIMEOUT_SECONDS` |
| `deepseek` | `deepseek` | `DEEPSEEK_ENABLED` | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` | `DEEPSEEK_TIMEOUT_SECONDS` |

## Policy Rules

- `AI_PROVIDER` is optional, but if set it must resolve to one of the four supported providers.
- `AI_PROVIDER_FALLBACK_ENABLED` defaults to `false`.
- `AI_PROVIDER_FALLBACK_ORDER` must only contain supported providers.
- `ALLOW_PAID_PROVIDER_SMOKE_TEST` defaults to `false`.
- `GROQ_API_KEY` is rejected by policy.
- Legacy `AI_PRIMARY_*` and `AI_FALLBACK_*` references are rejected when they still mention unsupported providers.

## Observed Validation

- `openclaw-advisor provider-policy --strict --project-root . --env-file .env.example --json` returned `BLOCKED` with `NO_ENABLED_PROVIDER`.
- `git grep -n -i groq -- .` returned no matches in the tracked tree.
- The ignored runtime snapshot now defaults to `openai/gpt-5.3-chat-latest`.

## Notes

- The shell environment still exposes historical provider credentials to `openclaw models status --json`, but the tracked code path no longer allows Groq selection.
