"""
This file contains tests for running the Dart Language Server.
"""

import pytest
from multilspy import LanguageServer
from multilspy.multilspy_config import Language
from tests.test_utils import create_test_context
from pathlib import PurePath

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_multilspy_dart_open_nutri_tracker():
    """
    Test the working of multilspy with a Dart repository.
    """
    code_language = Language.DART
    params = {
        "code_language": code_language,
        "repo_url": "https://github.com/simonoppowa/OpenNutriTracker/",
        "repo_commit": "2df39185bdd822dec6a0e521f4c14e3eab6b0805",
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(
            context.config, context.logger, context.source_directory
        )

        async with lsp.start_server():
            result = await lsp.request_document_symbols(
                str(
                    PurePath("lib/core/presentation/widgets/copy_or_delete_dialog.dart")
                )
            )

            assert isinstance(result, tuple)
            assert len(result) == 2

            symbols = result[0]
            for symbol in symbols:
                del symbol["deprecated"]
                del symbol["kind"]
                del symbol["location"]["uri"]

            assert symbols == [
                {
                    "location": {
                        "range": {
                            "end": {"character": 24, "line": 3},
                            "start": {"character": 6, "line": 3},
                        },
                    },
                    "name": "CopyOrDeleteDialog",
                },
                {
                    "containerName": "CopyOrDeleteDialog",
                    "location": {
                        "range": {
                            "end": {"character": 26, "line": 4},
                            "start": {"character": 8, "line": 4},
                        },
                    },
                    "name": "CopyOrDeleteDialog",
                },
                {
                    "containerName": "CopyOrDeleteDialog",
                    "location": {
                        "range": {
                            "end": {"character": 14, "line": 7},
                            "start": {"character": 9, "line": 7},
                        },
                    },
                    "name": "build",
                },
            ]

import asyncio

import shutil

NO_DART = shutil.which("dart") is None

@pytest.mark.asyncio
@pytest.mark.skipif(NO_DART, reason="dart not found")
async def test_multilspy_dart_diagnostics():
    """
    Test the diagnostic working of multilspy with dart repository
    """
    code_language = Language.DART
    params = {
        "code_language": code_language,
        "repo_url": "https://github.com/simonoppowa/OpenNutriTracker/",
        "repo_commit": "2df39185bdd822dec6a0e521f4c14e3eab6b0805"
    }
    with create_test_context(params) as context:
        import subprocess
        subprocess.run(["dart", "pub", "get"], cwd=context.source_directory, check=False)

        lsp = LanguageServer.create(context.config, context.logger, context.source_directory)
        async with lsp.start_server():
            file_path = "lib/core/presentation/widgets/copy_or_delete_dialog.dart"
            with lsp.open_file(file_path):
                # Clear any diagnostics received during file open to ensure we wait for the update triggered by our change
                lsp.diagnostics_received.clear()
                lsp.insert_text_at_position(file_path, 10, 0, "this is a syntax error")
                
                # Poll for diagnostics
                await lsp.await_diagnostics(timeout=60)
                diagnostics = await lsp.request_diagnostics(file_path)
                assert len(diagnostics) > 0

