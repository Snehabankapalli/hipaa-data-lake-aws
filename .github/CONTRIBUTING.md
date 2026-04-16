# Contributing Guidelines

## Development Setup

```bash
git clone https://github.com/Snehabankapalli/real-time-analytics-platform
cd real-time-analytics-platform

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install flake8 black isort mypy pytest pytest-cov
```

## Workflow

1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes and write tests
4. Run quality checks
5. Commit: `git commit -m 'feat: add your feature'`
6. Push and open a Pull Request

## Quality Standards

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/
pytest tests/ -v --cov=src --cov-fail-under=80
```

## Commit Format

`<type>: <description>` — types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

## Code Style

- Python: PEP 8 (enforced by Black)
- No hardcoded secrets — use environment variables
- Error handling at every level
- Functions under 50 lines

Questions? Open an issue or contact [@Snehabankapalli](https://github.com/Snehabankapalli)
