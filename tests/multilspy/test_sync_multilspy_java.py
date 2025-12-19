"""
This file contains tests for running the Java Language Server: Eclipse JDT.LS
"""

from pathlib import PurePath
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import Language
from tests.test_utils import create_test_context

def test_multilspy_java_clickhouse_highlevel_sinker() -> None:
    """
    Test the working of multilspy with Java repository - clickhouse-highlevel-sinker
    """
    code_language = Language.JAVA
    params = {
        "code_language": code_language,
        "repo_url": "https://github.com/Index103000/clickhouse-highlevel-sinker/",
        "repo_commit": "ee31d278918fe5e64669a6840c4d8fb53889e573"
    }
    with create_test_context(params) as context:
        lsp = SyncLanguageServer.create(context.config, context.logger, context.source_directory)

        # All the communication with the language server must be performed inside the context manager
        # The server process is started when the context manager is entered and is terminated when the context manager is exited.
        with lsp.start_server():
            filepath = str(PurePath("src/main/java/com/xlvchao/clickhouse/component/ClickHouseSinkManager.java"))
            result = lsp.request_definition(filepath, 44, 59)

            assert isinstance(result, list)
            assert len(result) == 1
            item = result[0]
            assert item["relativePath"] == str(
                PurePath("src/main/java/com/xlvchao/clickhouse/component/ScheduledCheckerAndCleaner.java")
            )
            assert item["range"] == {
                "start": {"line": 22, "character": 11},
                "end": {"line": 22, "character": 37},
            }

            # TODO: The following test is running flaky on Windows. Investigate and fix.
            # On Windows, it returns the correct result sometimes and sometimes it returns the following:
            # incorrect_output = [
            #     {
            #         "range": {"end": {"character": 86, "line": 24}, "start": {"character": 65, "line": 24}},
            #         "relativePath": "src\\main\\java\\com\\xlvchao\\clickhouse\\component\\ClickHouseSinkManager.java",
            #     },
            #     {
            #         "range": {"end": {"character": 61, "line": 2}, "start": {"character": 7, "line": 2}},
            #         "relativePath": "src\\test\\java\\com\\xlvchao\\clickhouse\\SpringbootDemo.java",
            #     },
            #     {
            #         "range": {"end": {"character": 29, "line": 28}, "start": {"character": 8, "line": 28}},
            #         "relativePath": "src\\test\\java\\com\\xlvchao\\clickhouse\\SpringbootDemo.java",
            #     },
            #     {
            #         "range": {"end": {"character": 69, "line": 28}, "start": {"character": 48, "line": 28}},
            #         "relativePath": "src\\test\\java\\com\\xlvchao\\clickhouse\\SpringbootDemo.java",
            #     },
            # ]

            result = lsp.request_references(filepath, 82, 27)

            assert isinstance(result, list)
            assert len(result) == 2

            for item in result:
                del item["uri"]
                del item["absolutePath"]

            assert result == [
                {
                    "relativePath": str(
                        PurePath("src/main/java/com/xlvchao/clickhouse/component/ClickHouseSinkManager.java")
                    ),
                    "range": {
                        "start": {"line": 75, "character": 66},
                        "end": {"line": 75, "character": 85},
                    },
                },
                {
                    "relativePath": str(
                        PurePath("src/main/java/com/xlvchao/clickhouse/component/ClickHouseSinkManager.java")
                    ),
                    "range": {
                        "start": {"line": 71, "character": 12},
                        "end": {"line": 71, "character": 31},
                    },
                },
            ]

def test_multilspy_java_diagnostics() -> None:
    """
    Test the request_diagnostics API by creating a Java file with syntax errors
    """
    import os
    import tempfile
    import time
    
    code_language = Language.JAVA
    
    # Create a temporary directory with a Java file containing syntax errors
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a Java file with syntax errors
        error_file = os.path.join(temp_dir, "ErrorFile.java")
        with open(error_file, "w") as f:
            f.write('''
// This file has syntax errors for testing diagnostics
public class ErrorFile {
    public void brokenMethod( {
        // Missing closing parenthesis
        
        int x = 1 +  // incomplete expression
        
        if (true
            System.out.println("missing parenthesis");
        
        String s = "unclosed string
    }
}
''')
        
        # Create a minimal config and test
        from multilspy.multilspy_config import MultilspyConfig
        from multilspy.multilspy_logger import MultilspyLogger
        
        config = MultilspyConfig.from_dict({"code_language": code_language})
        logger = MultilspyLogger()
        lsp = SyncLanguageServer.create(config, logger, temp_dir)

        with lsp.start_server():
            # Open the file to trigger diagnostic push from language server
            with lsp.open_file("ErrorFile.java"):
                # Wait for the language server to analyze and push diagnostics
                # Java LS takes longer to start up
                time.sleep(5.0)
                
                # Request diagnostics for the file with syntax errors (while file is open)
                result = lsp.request_diagnostics("ErrorFile.java")

            # Verify we got diagnostics
            assert isinstance(result, list), f"Expected list, got {type(result)}"
            assert len(result) >= 1, "Expected at least 1 diagnostic for file with syntax errors"

            # Verify diagnostics structure
            diag = result[0]
            assert "range" in diag, "Diagnostic should have 'range'"
            assert "message" in diag, "Diagnostic should have 'message'"
            assert "start" in diag["range"], "Range should have 'start'"
            assert "end" in diag["range"], "Range should have 'end'"
            
            # Verify it's an error with severity=1 (Error)
            assert diag.get("severity") == 1, f"Expected severity=1 (Error), got {diag.get('severity')}"
