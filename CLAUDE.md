# YT-to-Jellyfin Development Guidelines

## Build/Run Commands
- Run locally: `python3 app.py` or `docker-compose up`
- Web interface: `python3 app.py --web-only` (access at http://localhost:8000)
- Tests: `python run_tests.py` (runs all tests)
- Single test type: `python run_tests.py --type basic` (options: basic, api, job, integration, web)
- Docker test: `./test_docker.sh` (tests Docker build and functionality)
- Lint: `flake8 .`

## Continuous Integration
- Tests are automatically run on all commits
- Docker builds are verified on changes to Docker-related files
- PRs should pass all CI checks before merging

## Code Style Guidelines
- **Formatting**: Follow PEP 8, use Black formatter
- **Imports**: Group in order: standard library, third-party, local
- **Types**: Use type hints for function parameters and return values
- **Naming**: snake_case for functions/variables, UPPER_CASE for constants
- **Error Handling**: Use try/except blocks with specific exceptions
- **Comments**: Docstrings for classes and functions, # for inline comments
- **Docker**: Keep images minimal and secure, use multi-stage builds
- **Config**: Use environment variables for configuration
- **Tests**: All new features should include test coverage