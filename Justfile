set shell := ["bash", "-c"]

current_version := `grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3`
current_uid := `id -u $USER`
current_gid := `id -g $USER`
current_user := current_uid + ":" + current_gid
rootdir := justfile_directory()

image_name := env('IMAGE_NAME', 'eclipse_tracker')
image_version := env('IMAGE_VERSION', current_version)

# HELP AND INFORMATION
##############################################################################

# List available recipes
default:
    @just --list

# Show current project version
version:
    @echo {{current_version}}

# ENVIRONMENT SETUP
##############################################################################

# Check if direnv is installed
check-direnv:
    #!/usr/bin/env bash
    if ! command -v direnv &> /dev/null; then
        echo "Direnv is not installed. Please install direnv first."
        exit 1
    fi

# Check if git-lfs is installed
check-git-lfs:
    #!/usr/bin/env bash
    if ! command -v git-lfs &> /dev/null; then
        echo "Git LFS is not installed. Please install Git LFS first."
        echo "Visit: https://git-lfs.github.io/ for installation instructions"
        exit 1
    fi

# Set up development environment
setup-env:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Setting up development environment..."

    # Copy .env.example to .env if .env doesn't exist
    if [[ ! -f ".env" ]] && [[ -f ".env.example" ]]; then
        echo "Copying .env.example to .env..."
        cp .env.example .env
    fi

    # Check if uv is installed
    if ! command -v uv >/dev/null 2>&1; then
        echo "ERROR: uv package manager is not installed"
        echo "Please install uv first: https://docs.astral.sh/uv/"
        exit 1
    fi

    # Create lock file if it doesn't exist
    if [[ ! -f "uv.lock" ]]; then
        echo "Creating uv.lock file..."
        just env-lock
    fi

    # Create/sync virtual environment
    if [[ ! -d ".venv" ]] || ! uv run python --version >/dev/null 2>&1; then
        echo "Creating virtual environment..."
        just env-sync
    fi

# Set up git-lfs tracking
setup-git-lfs: check-git-lfs
    @git lfs install --local
    @git lfs track --lockable

# Set up pre-commit hooks
setup-git: setup-git-lfs
    @pre-commit install -t pre-push
    @pre-commit run --all-files

# Set up complete project environment
setup: setup-env
    @echo "Setup complete."
    @echo "If you want to use git:"
    @echo "  git init . --initial-branch=master"
    @echo "  just setup-git"

# Clean Python caches and build artifacts
clean:
    #!/usr/bin/env bash
    rm -rf .pytest_cache
    rm -rf build/
    rm -rf dist/
    rm -rf public/
    rm -rf docs/_build
    rm -rf *.egg-info
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "*.pyo" -delete 2>/dev/null || true

# Clean virtual environment
clean-env:
    #!/usr/bin/env bash
    if [[ -d ".venv" ]]; then
        echo "Removing .venv directory..."
        rm -rf .venv
        echo "Virtual environment removed."
    else
        echo "No .venv directory found."
    fi

# DEPENDENCY MANAGEMENT
##############################################################################

# Lock dependencies to specific versions (pass extra args)
env-lock *args="":
    uv lock {{args}}

# Sync dependencies with lockfile (pass extra args)
env-sync *args="":
    uv sync {{args}}

# List installed dependencies (pass extra args)
env-list *args="":
    uv tree {{args}}

# Add dependencies (add --group dev or --group docs for non-production dependencies)
env-add *args:
    #!/usr/bin/env bash
    if [[ -z "{{args}}" ]]; then
        echo "Usage: just env-add [--group GROUP] package1 package2 ..."
        echo "Examples:"
        echo "  just env-add requests fastapi           # Add production dependencies"
        echo "  just env-add --group dev pytest ruff    # Add development dependencies"
        echo "  just env-add --group docs mkdocs        # Add documentation dependencies"
        exit 1
    fi
    uv add {{args}}

# Update dependencies (add --group dev or --group docs to update specific groups)
env-update *args="":
    #!/usr/bin/env bash
    if [[ -z "{{args}}" ]]; then
        echo "Updating all dependencies..."
        uv lock --upgrade
    else
        echo "Updating with args: {{args}}"
        uv lock --upgrade {{args}}
    fi

# VERSIONING
##############################################################################

# Bump version (usage: just version-bump MAJOR|MINOR|PATCH or just version-bump 1.2.3)
version-bump increment *extra_args="":
    #!/usr/bin/env bash
    if [[ -z "{{increment}}" ]]; then
        echo "Usage: just version-bump MAJOR|MINOR|PATCH [extra_args]"
        echo "   or: just version-bump 1.2.3 [extra_args]"
        exit 1
    fi

    increment="{{increment}}"
    extra_args="{{extra_args}}"

    if [[ "$increment" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        # Specific version format (e.g., 1.2.3)
        uv run cz bump "$increment" $extra_args
    else
        # Increment type (MAJOR, MINOR, PATCH)
        uv run cz bump --increment "$increment" $extra_args
    fi

# CODE QUALITY AND TESTING
##############################################################################

# Run small and medium tests
test: test-s test-m

# Run small tests (pass extra args, e.g. coverage flags)
test-s *args="":
    #!/usr/bin/env bash
    uv run pytest tests/small \
        --html=docs/_build/test-reports/small-test/index.html \
        --junitxml=docs/_build/test-reports/small-test/junit.xml \
        -o junit_suite_name=small-test \
        {{args}}

# Run medium tests (pass extra args, e.g. coverage flags)
test-m *args="":
    #!/usr/bin/env bash
    uv run pytest tests/medium \
        --gherkin-terminal-reporter \
        --html=docs/_build/test-reports/medium-test/index.html \
        --junitxml=docs/_build/test-reports/medium-test/junit.xml \
        -o junit_suite_name=medium-test \
        {{args}}

# Run large tests (no coverage - these run against deployed systems)
test-l *args="":
    #!/usr/bin/env bash
    uv run pytest tests/large \
        --html=docs/_build/test-reports/large-test/index.html \
        --junitxml=docs/_build/test-reports/large-test/junit.xml \
        -o junit_suite_name=large-test \
        {{args}}

# Run small and medium tests with combined coverage report
coverage:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Running small tests with coverage..."
    COVERAGE_FILE=docs/_build/coverage/small-test/.coverage \
    just test-s \
        --cov src \
        --cov-report term-missing \
        --cov-report html:docs/_build/coverage/small-test \
        --cov-report xml:docs/_build/coverage/small-test/coverage.xml

    echo "Running medium tests with coverage..."
    COVERAGE_FILE=docs/_build/coverage/medium-test/.coverage \
    just test-m \
        --cov src \
        --cov-report term \
        --cov-report html:docs/_build/coverage/medium-test \
        --cov-report xml:docs/_build/coverage/medium-test/coverage.xml

    echo "Generating combined coverage report..."
    uv run coverage combine --keep \
        docs/_build/coverage/small-test/.coverage \
        docs/_build/coverage/medium-test/.coverage
    uv run coverage report --fail-under=90
    uv run coverage html -d docs/_build/coverage/total
    uv run coverage xml -o docs/_build/coverage/total/coverage.xml

# Format code with ruff (pass extra args)
format *args="":
    uv run ruff format {{args}} .

# Lint code with ruff (pass extra args)
lint *args="":
    #!/usr/bin/env bash
    if ! uv run ruff check {{args}} src; then
        echo ""
        echo "Linting failed! Review the changes and/or use --fix and/or --unsafe-fixes for auto-repair"
        echo "Examples:"
        echo "  just lint --fix                  # Apply safe fixes"
        echo "  just lint --fix --unsafe-fixes   # Apply all available fixes"
        exit 1
    fi

# Run security analysis (pass extra args)
security *args="":
    uv run bandit -v -r src/eclipse_tracker {{args}}

# Run all code quality checks
check: format lint

# DOCUMENTATION
##############################################################################

# Build complete documentation
docs: docs-generate-openapi docs-build

# Build documentation site (pass extra args)
docs-build *args="":
    uv run mkdocs build --verbose --strict {{args}}

# Generate OpenAPI documentation (pass extra args)
docs-generate-openapi *args="":
    uv run python scripts/gen_openapi_implemented.py {{args}}

# Serve documentation locally (pass extra args)
docs-serve *args="":
    uv run mkdocs serve --dev-addr=0.0.0.0:8001 --verbose {{args}}

# BUILD AND DEPLOYMENT
##############################################################################

# Build package distribution (pass extra args)
dist *args="":
    uv build {{args}}

# Serve application locally (pass extra args)
serve *args="":
    uv run uvicorn src.eclipse_tracker.app:app --reload --port 8080 {{args}}

# DOCKER OPERATIONS
##############################################################################

# Start docker services
docker-start containers="":
    #!/usr/bin/env bash
    if [[ -z "{{containers}}" ]]; then
        echo "Starting all docker-compose.*.yml services..."
        for compose_file in docker/docker-compose.*.yml; do
            if [[ -f "$compose_file" ]] && [[ "$compose_file" != "docker/docker-compose-dev.yml" ]]; then
                echo "Starting $compose_file..."
                ROOTDIR={{rootdir}} \
                    docker compose -f "$compose_file" \
                    up -d --remove-orphans
            fi
        done
    else
        IFS='+' read -ra container_array <<< "{{containers}}"
        for container in "${container_array[@]}"; do
            compose_file="docker/docker-compose.${container}.yml"
            if [[ -f "$compose_file" ]]; then
                echo "Starting $compose_file..."
                ROOTDIR={{rootdir}} \
                    docker compose -f "$compose_file" \
                    up -d --remove-orphans
            fi
        done
    fi

# Stop docker services
docker-stop containers="":
    #!/usr/bin/env bash
    if [[ -z "{{containers}}" ]]; then
        echo "Stopping all docker-compose.*.yml services..."
        for compose_file in docker/docker-compose.*.yml; do
            if [[ -f "$compose_file" ]] && [[ "$compose_file" != "docker/docker-compose-dev.yml" ]]; then
                echo "Stopping $compose_file..."
                ROOTDIR={{rootdir}} \
                    docker compose -f "$compose_file" \
                    rm -f -s -v
            fi
        done
    else
        IFS='+' read -ra container_array <<< "{{containers}}"
        for container in "${container_array[@]}"; do
            compose_file="docker/docker-compose.${container}.yml"
            if [[ -f "$compose_file" ]]; then
                echo "Stopping $compose_file..."
                ROOTDIR={{rootdir}} \
                    docker compose -f "$compose_file" \
                    rm -f -s -v
            fi
        done
    fi

# Run command in docker container
docker-run *args="":
    #!/usr/bin/env bash
    if [[ -z "{{args}}" ]]; then
        cmd="just --list"
    else
        cmd="{{args}}"
    fi

    echo "Running command in container: $cmd"
    ROOTDIR={{rootdir}} \
        docker compose -f docker/docker-compose-dev.yml \
        run --rm --remove-orphans \
        eclipse_tracker-dev bash -c "$cmd"

# Open shell in docker container
docker-shell:
    #!/usr/bin/env bash
    ROOTDIR={{rootdir}} \
        docker compose -f docker/docker-compose-dev.yml \
        run --rm eclipse_tracker-dev /bin/bash

# Lint Dockerfile
docker-lint:
    docker run --rm -i \
        hadolint/hadolint \
        hadolint - < docker/Dockerfile

# Build production docker image
docker-build revision="local-dev":
    #!/usr/bin/env bash
    DOCKER_BUILDKIT=1 docker build --pull -f docker/Dockerfile \
        --progress=plain \
        --build-arg VERSION={{image_version}} \
        --build-arg REVISION={{revision}} \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        -t {{image_name}}:{{image_version}} \
        .
    echo "Image built: {{image_name}}:{{image_version}}"
    echo "Run the container to test with: docker run -p 8080:8080 {{image_name}}:{{image_version}}"
    echo "Or inspect it from bash: docker run -it -p 8080:8080 --entrypoint /bin/bash {{image_name}}:{{image_version}}"

# CUSTOM PROJECT COMMANDS
##############################################################################

api_host := env('API_HOST', 'http://localhost:8080')

# Install frontend npm dependencies
frontend-install:
    cd frontend && npm install

# Run the frontend Vite dev server (pass extra args)
frontend-dev *args="":
    cd frontend && npm run dev -- {{args}}

# Build the frontend for production (pass extra args)
frontend-build *args="":
    cd frontend && npm run build -- {{args}}

# Lint the frontend (pass extra args)
frontend-lint *args="":
    cd frontend && npm run lint -- {{args}}

# Preview the frontend production build (pass extra args)
frontend-preview *args="":
    cd frontend && npm run preview -- {{args}}

# Run backend and frontend dev servers together (Ctrl-C stops both)
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT
    just serve &
    just frontend-dev &
    wait

# List all bundled eclipses (curl helper)
eclipses-list:
    curl -s {{api_host}}/api/eclipses | python3 -m json.tool

# Get ranked viewing-location recommendations for a point (curl helper)
recommend lat lon range_km="150":
    curl -s -X POST {{api_host}}/api/recommendations \
        -H "Content-Type: application/json" \
        -d '{"lat": {{lat}}, "lon": {{lon}}, "range_km": {{range_km}}}' \
        | python3 -m json.tool

# Get a day-of itinerary for a chosen candidate (curl helper)
itinerary candidate_id candidate_name eclipse_id lat lon:
    curl -s -G {{api_host}}/api/itinerary \
        --data-urlencode "candidate_id={{candidate_id}}" \
        --data-urlencode "candidate_name={{candidate_name}}" \
        --data-urlencode "eclipse_id={{eclipse_id}}" \
        --data-urlencode "lat={{lat}}" \
        --data-urlencode "lon={{lon}}" \
        | python3 -m json.tool

# TEMPLATE UTILS
##############################################################################

# Check if the project uses the latest stable template
check-template-update:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -f ".copier-answers.yml" ]]; then
        echo "No .copier-answers.yml found; cannot determine current template tag."
        exit 1
    fi
    # Extract current tag like vX.Y.Z from _commit
    CURRENT_TEMPLATE_TAG=$(grep -m1 '^_commit:' .copier-answers.yml || true)
    CURRENT_TEMPLATE_TAG=$(echo "$CURRENT_TEMPLATE_TAG" | sed -E 's/_commit:[[:space:]]*(v[0-9]+\.[0-9]+\.[0-9]+).*/\1/')
    if [[ -z "$CURRENT_TEMPLATE_TAG" ]]; then
        echo "Error: CURRENT_TEMPLATE_TAG is empty. Check '_commit' in .copier-answers.yml."
        exit 1
    fi

    if [[ "${CI:-}" = "true" ]]; then
        TEMPLATE_URL="https://github.com/greg0109/copier-python-http.git"
    else
        TEMPLATE_URL="git@github.com:greg0109/copier-python-http.git"
    fi

    # Get latest tag from remote
    LATEST_TEMPLATE_TAG=$(git ls-remote --tags "$TEMPLATE_URL" 2>/dev/null || true)
    LATEST_TEMPLATE_TAG=$(echo "$LATEST_TEMPLATE_TAG" | grep -v '\^{}' | cut -d/ -f3 | sort -V | tail -n1 || true)
    if [[ -z "$LATEST_TEMPLATE_TAG" ]]; then
        echo "Error: Could not determine LATEST_TEMPLATE_TAG from the template repository."
        exit 1
    fi

    echo "Current template version: $CURRENT_TEMPLATE_TAG"
    echo "Latest available version: $LATEST_TEMPLATE_TAG"
    if [[ "$CURRENT_TEMPLATE_TAG" = "$LATEST_TEMPLATE_TAG" ]]; then
        echo "The project is using the latest version of the template."
    else
        echo "The project is NOT using the latest version of the template."
        echo "Consider running: copier update"
        exit 1
    fi
