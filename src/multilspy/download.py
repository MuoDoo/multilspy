"""
Pre-download CLI for multilspy language server dependencies.

This module provides a command-line tool to pre-download the runtime
dependencies for language servers, avoiding long waits during first use.

Usage:
    multilspy-download --language java
    multilspy-download --language python
    multilspy-download --all
"""

import argparse
import logging
import os
import sys
import time

from multilspy.multilspy_logger import MultilspyLogger
from multilspy.multilspy_config import MultilspyConfig, Language


def download_java_dependencies(logger: MultilspyLogger) -> None:
    """Pre-download Eclipse JDT.LS dependencies."""
    print("Downloading Java (Eclipse JDT.LS) dependencies...")
    start_time = time.time()
    
    from multilspy.language_servers.eclipse_jdtls.eclipse_jdtls import EclipseJDTLS
    
    # Create a temporary config to trigger dependency download
    config = MultilspyConfig.from_dict({"code_language": Language.JAVA})
    
    # setupRuntimeDependencies will download if not present
    # We need to call it directly without starting the full server
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a minimal Java file so the server can initialize
        java_file = os.path.join(temp_dir, "Main.java")
        with open(java_file, "w") as f:
            f.write("public class Main { public static void main(String[] args) {} }")
        
        # This will download dependencies
        jdtls = EclipseJDTLS(config, logger, temp_dir)
        
    elapsed = time.time() - start_time
    print(f"✓ Java dependencies ready ({elapsed:.1f}s)")


def download_python_dependencies(logger: MultilspyLogger) -> None:
    """Pre-download Python (jedi-language-server) dependencies."""
    print("Downloading Python (jedi-language-server) dependencies...")
    start_time = time.time()
    
    # jedi-language-server is installed as a pip dependency, no runtime download needed
    try:
        import jedi
        print(f"✓ Python dependencies ready (jedi {jedi.__version__})")
    except ImportError:
        print("✗ jedi-language-server not installed. Run: pip install jedi-language-server")
        sys.exit(1)
    
    elapsed = time.time() - start_time
    print(f"  Completed in {elapsed:.1f}s")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-download multilspy language server dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    multilspy-download --language java     # Download Java dependencies
    multilspy-download --language python   # Verify Python dependencies
    multilspy-download --all               # Download all dependencies
        """
    )
    
    parser.add_argument(
        "--language", "-l",
        choices=["java", "python"],
        help="Language server to download dependencies for"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Download dependencies for all supported languages"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if not args.language and not args.all:
        parser.print_help()
        sys.exit(1)
    
    # Setup logger
    logger = MultilspyLogger()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    print("=" * 50)
    print("multilspy Dependency Downloader")
    print("=" * 50)
    
    if args.all:
        download_python_dependencies(logger)
        download_java_dependencies(logger)
    elif args.language == "java":
        download_java_dependencies(logger)
    elif args.language == "python":
        download_python_dependencies(logger)
    
    print("=" * 50)
    print("Done!")


if __name__ == "__main__":
    main()
