# Decision Cache — Check Here First
# Hit = use directly, no re-analysis needed

## Model Selection
| Scenario | Model | Reason |
|----------|-------|--------|
| Cron/monitoring | sonnet | Fast + cheap |
| Coding/debugging | opus | Balanced |
| Architecture/decisions | opus-4-6 | Strongest |

## Search Strategy
DDG web_fetch → Target URL direct → Browser Google (fallback)

## Session Management
Context > 50% → Start new session

## Reporting Rules
- Major ops: announce before
- Over 30s: send progress
- Complete: brief report
- No change → silent NO_REPLY

## Cost Rules
- Stability > savings > speed
- Earning > saving
- No-output cron → reduce frequency or kill

## Common Errors (Skip Analysis)
| Error | Fix |
|-------|-----|
| DDG captcha | Access target URL directly |
| Command not found | Check PATH or install |
| API timeout | Retry with backoff |
| Rate limit | Wait and retry |
