# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you believe you have found a security vulnerability:

- **Do not** open a public issue describing it.
- Report it privately by email or through GitHub's Security Advisories
  ("Report a vulnerability") flow on this repository.
- Include a description of the issue, how to reproduce it, and the affected
  version.

You will receive a response within 5 business days, and we will coordinate a
fix before disclosing details publicly.

## Security considerations

- The project embeds documents and may run retrieval/LLM pipelines. Treat
  embedded content and model output as untrusted.
- Never commit real credentials, API keys, or tokens. Use environment
  variables or a secret manager.
- Review the `.github/workflows`, `grafana/`, `prometheus/`, and `k8s/`
  configurations for secret handling before deploying to a shared environment.
