#!/usr/bin/env python3
"""
Generate openapi specification from implementation.

This script extracts the implemented OpenAPI definition and saves it to a specified file
in the docs folder.

Parameters
----------
- filename: str, optional
    The path where the generated OpenAPI specification file will be saved.
    Default is 'docs/reference/api/openapi-developed.json'.

Usage
-----
Run this script to extract the OpenAPI definition and save it to a file.
Optionally, specify a different filename to save the OpenAPI specification to a different file.

Example:
    python gen_openapi_implemented.py --help
"""

import json
import sys
from pathlib import Path

import typer
from fastapi.openapi.utils import get_openapi


sys.path.append(str(Path.cwd()))  # Find app locally
from src.eclipse_tracker.app import app


cli = typer.Typer()


@cli.command()
def main(filename: str = "docs/references/integration/api/openapi-developed.json") -> None:
    """Generate openapi spec."""
    typer.echo(f"Generating latest version of the implemented API in: {filename}")
    with Path(filename).open("w", encoding="utf-8") as fd:
        json.dump(
            get_openapi(
                title=app.title,
                version=app.version,
                openapi_version=app.openapi_version,
                description=app.description,
                routes=app.routes,
            ),
            fd,
            indent=4,
        )
        typer.echo("done.")


if __name__ == "__main__":
    cli()
