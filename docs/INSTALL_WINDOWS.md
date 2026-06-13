# Windows Installation

1. Install Node.js 24.x.
2. Install Python 3.12.x.
3. Run `iwr -useb https://openclaw.ai/install.ps1 | iex`.
4. Fill `C:\Data\OpenClawSuperAdvisor\state\.env`.
5. Validate with `openclaw config validate --json` and the unit tests.
