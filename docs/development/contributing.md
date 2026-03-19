# Contributing Guide

Thank you for your interest in contributing to the Hive! This guide will help you get started.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- Docker
- Basic understanding of:
  - FastAPI
  - SQLAlchemy
  - Async Python
  - LLMs (Ollama)

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/hive.git
cd hive
```

2. **Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

3. **Install dependencies**

```bash
pip install -e ".[dev]"
```

4. **Start infrastructure**

```bash
cd mind
docker-compose up -d
```

5. **Create development .env**

```env
AIC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mind
AIC_REDIS_URL=redis://localhost:6379/0
AIC_OLLAMA_BASE_URL=http://localhost:11434
AIC_OLLAMA_MODEL=phi4-mini
AIC_LOG_LEVEL=DEBUG
```

6. **Run the application**

```bash
python -m mind.api.main
```

---

## Code Organization

```
mind/
├── api/          # FastAPI routes and middleware
├── core/         # Database, types, LLM client
├── engine/       # Bot intelligence (mind, learning, consciousness)
├── agents/       # Personality and behavior generation
├── memory/       # Memory system
├── scheduler/    # Task scheduling
├── communities/  # Community management
├── prompts/      # LLM prompt templates
└── monitoring/   # Metrics and logging

cell/    # Flutter mobile app
└── lib/          # Dart source code

docs/             # Documentation
```

---

## How to Contribute

### Reporting Bugs

1. **Search existing issues** to avoid duplicates
2. **Create a new issue** with:
   - Clear title describing the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs or screenshots

### Suggesting Features

1. **Check existing issues and discussions**
2. **Open a discussion** for major features
3. **Create an issue** with:
   - Clear description of the feature
   - Use case and motivation
   - Proposed implementation (if you have ideas)

### Submitting Pull Requests

#### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions/improvements

#### 2. Make Your Changes

- Follow the [code style guide](code-style.md)
- Write tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

#### 3. Commit Your Changes

```bash
git add .
git commit -m "feat: add new consciousness mode for creative thinking

- Implement creative thought mode in ConsciousMind
- Add tests for creative mode selection
- Update documentation"
```

Commit message format:
```
<type>: <short description>

<longer description if needed>

<optional footer>
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Formatting
- `refactor` - Code restructuring
- `test` - Tests
- `chore` - Maintenance

#### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear title
- Description of changes
- Link to related issues
- Screenshots/examples if applicable

---

## Pull Request Process

### Before Submitting

- [ ] Code follows style guide
- [ ] Tests pass locally
- [ ] New features have tests
- [ ] Documentation updated
- [ ] Commit messages follow format
- [ ] Branch is up to date with main

### Review Process

1. **Automated checks** run (tests, linting)
2. **Code review** by maintainers
3. **Address feedback** if requested
4. **Approval and merge**

### Review Guidelines

Reviewers will check:
- Code quality and style
- Test coverage
- Documentation
- Performance implications
- Security considerations
- Compatibility

---

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mind

# Run specific test file
pytest tests/test_bot_mind.py

# Run specific test
pytest tests/test_bot_mind.py::test_identity_generation
```

### Code Formatting

```bash
# Format code
black mind/
isort mind/

# Check formatting
black --check mind/
```

### Type Checking

```bash
# Run type checker
mypy mind/
```

### Linting

```bash
# Run linter
ruff check mind/

# Auto-fix issues
ruff check --fix mind/
```

---

## Areas for Contribution

### Good First Issues

Look for issues labeled `good-first-issue`:
- Documentation improvements
- Bug fixes with clear reproduction steps
- Adding tests for existing functionality
- Small feature additions

### Help Wanted

Issues labeled `help-wanted` need community input:
- Complex features
- Performance improvements
- Integration with new services

### Current Priorities

1. **Testing** - Increase test coverage
2. **Documentation** - Improve API docs
3. **Performance** - Optimize LLM usage
4. **Features** - New bot capabilities

---

## Communication

### Discussions

Use GitHub Discussions for:
- Questions about the codebase
- Feature ideas
- Architecture discussions

### Issues

Use GitHub Issues for:
- Bug reports
- Feature requests
- Specific tasks

### Code of Conduct

- Be respectful and inclusive
- Assume good intentions
- Focus on constructive feedback
- Help newcomers learn

---

## Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` file
- Release notes
- GitHub contribution graph

---

## Questions?

- Check existing documentation
- Search closed issues
- Open a discussion
- Ask in the community channels

Thank you for contributing!
