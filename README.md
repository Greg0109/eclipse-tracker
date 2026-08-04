# Eclipse Tracker

- Check out the [technical documentation](https://greg0109/eclipse_tracker)

## Prerequisites

- Install [just](https://github.com/casey/just#installation)
- Install [uv](https://docs.astral.sh/uv/)
- Copy `.env.example` to `.env` and fill in your credentials

Optional:

- Install [direnv](https://direnv.net/)
- Run `direnv allow` for automatic environment activation

## Quickstart

```bash
# Env (without direnv)
just env-lock
just env-sync

# Linting
just lint --fix     # Apply safe fixes via execute uv run ruff check --fix src with a nice help command instructions if linting fails
just check          # Execute format and lint

# Environment management
just env-add --help    # Prints uv add help
just env-add --group docs mkdocs-mermaid2-plugin
just env-add --group docs mkdocs-material-extensions

# Development workflow
just docs            # Generate documentation
just test            # Run small and medium tests
just coverage        # Run tests with coverage report
just docker-start    # Start all Docker compose services automatically
just serve

# Production
just docker-build
```
