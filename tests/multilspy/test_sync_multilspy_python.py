"""
This file contains tests for running the Python Language Server: jedi-language-server
"""

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import Language
from tests.test_utils import create_test_context
from pathlib import PurePath

def test_multilspy_python_black() -> None:
    """
    Test the working of multilspy with python repository - black
    """
    code_language = Language.PYTHON
    params = {
        "code_language": code_language,
        "repo_url": "https://github.com/psf/black/",
        "repo_commit": "f3b50e466969f9142393ec32a4b2a383ffbe5f23"
    }
    with create_test_context(params) as context:
        lsp = SyncLanguageServer.create(context.config, context.logger, context.source_directory)

        # All the communication with the language server must be performed inside the context manager
        # The server process is started when the context manager is entered and is terminated when the context manager is exited.
        with lsp.start_server():
            result = lsp.request_definition(str(PurePath("src/black/mode.py")), 163, 4)

            assert isinstance(result, list)
            assert len(result) == 1
            item = result[0]
            assert item["relativePath"] == str(PurePath("src/black/mode.py"))
            assert item["range"] == {
                "start": {"line": 163, "character": 4},
                "end": {"line": 163, "character": 20},
            }

            result = lsp.request_references(str(PurePath("src/black/mode.py")), 163, 4)

            assert isinstance(result, list)
            assert len(result) == 8

            for item in result:
                del item["uri"]
                del item["absolutePath"]

            assert result == [
                {
                    "relativePath": str(PurePath("src/black/__init__.py")),
                    "range": {
                        "start": {"line": 71, "character": 4},
                        "end": {"line": 71, "character": 20},
                    },
                },
                {
                    "relativePath": str(PurePath("src/black/__init__.py")),
                    "range": {
                        "start": {"line": 1105, "character": 11},
                        "end": {"line": 1105, "character": 27},
                    },
                },
                {
                    "relativePath": str(PurePath("src/black/__init__.py")),
                    "range": {
                        "start": {"line": 1113, "character": 11},
                        "end": {"line": 1113, "character": 27},
                    },
                },
                {
                    "relativePath": str(PurePath("src/black/mode.py")),
                    "range": {
                        "start": {"line": 163, "character": 4},
                        "end": {"line": 163, "character": 20},
                    },
                },
                {
                    "relativePath": str(PurePath("src/black/parsing.py")),
                    "range": {
                        "start": {"line": 7, "character": 68},
                        "end": {"line": 7, "character": 84},
                    },
                },
                {
                    "relativePath": str(PurePath("src/black/parsing.py")),
                    "range": {
                        "start": {"line": 37, "character": 11},
                        "end": {"line": 37, "character": 27},
                    },
                },
                {
                    "relativePath": str(PurePath("src/black/parsing.py")),
                    "range": {
                        "start": {"line": 39, "character": 14},
                        "end": {"line": 39, "character": 30},
                    },
                },
                {
                    "relativePath": str(PurePath("src/black/parsing.py")),
                    "range": {
                        "start": {"line": 44, "character": 11},
                        "end": {"line": 44, "character": 27},
                    },
                },
            ]


def test_multilspy_python_diagnostics() -> None:
    """
    Test the request_diagnostics API by creating a file with syntax errors
    """
    import os
    import tempfile
    import time
    
    code_language = Language.PYTHON
    
    # Create a temporary directory with a Python file containing syntax errors
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a Python file with syntax errors
        error_file = os.path.join(temp_dir, "error_file.py")
        with open(error_file, "w") as f:
            f.write('''
# This file has syntax errors for testing diagnostics
def broken_function(
    # Missing closing parenthesis and colon

x = 1 +  # incomplete expression

if True
    print("missing colon")

class Foo
    pass
''')
        
        # Create a minimal config and test
        from multilspy.multilspy_config import MultilspyConfig
        from multilspy.multilspy_logger import MultilspyLogger
        
        config = MultilspyConfig.from_dict({"code_language": code_language})
        logger = MultilspyLogger()
        lsp = SyncLanguageServer.create(config, logger, temp_dir)

        with lsp.start_server():
            # Open the file to trigger diagnostic push from language server
            with lsp.open_file("error_file.py"):
                # Wait a bit for the language server to analyze and push diagnostics
                time.sleep(2.0)
            
            # Request diagnostics for the file with syntax errors
            result = lsp.request_diagnostics("error_file.py")

            # Verify we got diagnostics
            assert isinstance(result, list), f"Expected list, got {type(result)}"
            assert len(result) >= 1, "Expected at least 1 diagnostic for file with syntax errors"

            # Verify diagnostics structure and content
            diag = result[0]
            assert "range" in diag, "Diagnostic should have 'range'"
            assert "message" in diag, "Diagnostic should have 'message'"
            assert "start" in diag["range"], "Range should have 'start'"
            assert "end" in diag["range"], "Range should have 'end'"
            
            # Verify it's a syntax error with severity=1 (Error)
            assert diag.get("severity") == 1, f"Expected severity=1 (Error), got {diag.get('severity')}"
            assert "SyntaxError" in diag["message"], f"Expected SyntaxError in message, got: {diag['message']}"
