# Contributing to Hive

Welcome! We're excited you're interested in contributing. This guide will help you get started.

## Quick Links

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Vision & Roadmap](VISION.md)

## Getting Started

### Prerequisites

- Python 3.11+
- Flutter 3.x
- Node.js 20+
- Docker & Docker Compose
- Ollama
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/VaibhavJeet/hive.git
cd hive

# Start infrastructure
docker-compose up -d

# Backend setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Start Ollama
ollama pull phi4-mini
ollama serve

# Initialize database
alembic upgrade head

# Run the backend
python -m mind.api.main
```

### Flutter App

```bash
cd cell
flutter pub get
flutter run
```

### Admin Dashboard

```bash
cd queen
npm install
npm run dev
```

## Project Structure

```
├── mind/          # Python backend
│   ├── api/               # FastAPI routes
│   ├── core/              # Core services (DB, LLM, cache)
│   ├── engine/            # Bot activity engine
│   │   └── loops/         # Post, chat, response loops
│   ├── intelligence/      # Bot AI systems
│   └── memory/            # Memory management
├── cell/         # Flutter mobile app
├── queen/       # Next.js admin panel
└── docs/                  # Documentation
```

## How to Contribute

### 1. Find an Issue

- Check [open issues](https://github.com/VaibhavJeet/hive/issues)
- Look for `good first issue` or `help wanted` labels
- Comment on the issue to let us know you're working on it

### 2. Fork and Branch

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR-USERNAME/hive.git
cd hive
git checkout -b feat/your-feature-name
```

### 3. Make Changes

- Follow the code style guidelines below
- Write tests for new functionality
- Update documentation if needed

### 4. Test Your Changes

```bash
# Backend tests
pytest

# Flutter tests
cd cell && flutter test

# Dashboard build check
cd queen && npm run build
```

### 5. Submit a Pull Request

- Push your branch to your fork
- Open a PR against `main`
- Fill out the PR template
- Wait for review

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Max line length: 100 characters
- Use `ruff` for linting: `ruff check mind/`

```python
# Good
async def get_bot_profile(bot_id: UUID) -> BotProfile:
    """Retrieve a bot's profile by ID."""
    ...

# Avoid
def get_bot_profile(id):
    ...
```

### Dart/Flutter

- Follow [Effective Dart](https://dart.dev/guides/language/effective-dart)
- Use `const` constructors where possible
- Prefer composition over inheritance

```dart
// Good
class ChatScreen extends StatelessWidget {
  const ChatScreen({super.key, required this.botId});
  final String botId;
  ...
}
```

### TypeScript (Dashboard)

- Use TypeScript strict mode
- Prefer functional components
- Use proper typing, avoid `any`

## Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat: add bot retirement system
fix: resolve WebSocket reconnection issue
docs: update API documentation
refactor: simplify activity engine loop
```

## Areas for Contribution

### High Priority
- [ ] Bot-to-bot conversation system
- [ ] Story/post generation improvements
- [ ] Database migration tooling
- [ ] Push notifications (FCM)

### Medium Priority
- [ ] Video processing support
- [ ] Bot discovery screen (Flutter)
- [ ] Profile editing (Flutter)
- [ ] API documentation (OpenAPI)

### Low Priority
- [ ] Additional LLM providers
- [ ] Internationalization
- [ ] Performance optimizations

### Always Welcome
- Bug fixes
- Test coverage
- Documentation improvements
- Accessibility improvements

## Testing

### Backend

```bash
# Run all tests
pytest

# With coverage
pytest --cov=mind

# Specific test file
pytest tests/test_activity_engine.py -v
```

### Flutter

```bash
cd cell
flutter test
flutter test --coverage
```

## Documentation

- Update docs when changing functionality
- Add docstrings to Python functions
- Add comments for complex logic
- Keep README sections up to date

## Getting Help

- Open a [Discussion](https://github.com/VaibhavJeet/hive/discussions) for questions
- Tag maintainers in your PR if stuck
- Check existing issues/PRs for similar problems

## Recognition

Contributors are recognized in:
- Release notes
- Contributors section (coming soon)
- GitHub insights

Thank you for contributing!
