# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to the maintainers directly. You should
receive a response within 48 hours. If for some reason you do not, please
follow up to ensure we received your original message.

Please include:

- Type of issue (e.g., SQL injection, XSS, authentication bypass)
- Full paths of source file(s) related to the issue
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue

## Security Considerations

### Bot-Generated Code Execution

The self-coding sandbox (`mind/scaling/self_coding_sandbox.py`) executes
bot-generated Python code. Security measures include:

- Restricted imports (no os, subprocess, sys)
- Execution timeout limits
- Memory constraints
- Output size limits
- Code validation before execution

### Database Security

- All user inputs are parameterized (SQLAlchemy ORM)
- pgvector extension for memory embeddings
- Connection pooling with asyncpg

### API Security

- JWT-based authentication
- Rate limiting on all endpoints
- Input validation via Pydantic models
- CORS configuration required for production

### LLM Security

- Prompt injection mitigation in system prompts
- Content moderation for user-facing content
- No storage of raw API keys in code

## Best Practices for Contributors

1. Never commit secrets or API keys
2. Use environment variables for all credentials
3. Validate all user inputs
4. Use parameterized queries (ORM handles this)
5. Keep dependencies updated
6. Run `pip audit` periodically
