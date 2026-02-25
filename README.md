# Imperecta

## Security

The project uses automated security checks in CI:

- **Backend**: Bandit (SAST), Safety, pip-audit for Python dependencies
- **Frontend**: npm audit, eslint-plugin-security
- **Secrets**: Gitleaks for detecting leaked credentials
- **Snyk**: Dependency scanning and SAST (requires `SNYK_TOKEN` in GitHub secrets)

Run locally:
- Backend: `bandit -r backend/app/ -c backend/security.cfg`, `safety check`, `pip-audit`
- Frontend: `npm run audit`, `npm run lint:security`
