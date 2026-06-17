from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import urllib.request

logger = logging.getLogger(__name__)

_INSTALL_SCRIPT_URL = (
    "https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh"
)


def run() -> None:
    if not getattr(sys, "frozen", False):
        logger.error(
            "`merakisync update` is only supported for binary installs. "
            "To update a pip-installed library run:\n"
            "    pip install --upgrade merakisync\n"
            "    merakisync migrate"
        )
        sys.exit(1)

    binary_path = sys.executable
    install_dir = os.path.dirname(os.path.abspath(binary_path))

    logger.info("Downloading install script...")
    try:
        with urllib.request.urlopen(_INSTALL_SCRIPT_URL) as resp:
            script_bytes = resp.read()
    except Exception as exc:
        logger.error(
            "Failed to download install script: %s\n"
            "Run the update manually:\n"
            "    curl -LsSf %s | sh\n"
            "    merakisync migrate",
            exc,
            _INSTALL_SCRIPT_URL,
        )
        sys.exit(1)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sh")
    try:
        os.write(tmp_fd, script_bytes)
        os.close(tmp_fd)

        result = subprocess.run(["sh", tmp_path, "--install-dir", install_dir])
        if result.returncode != 0:
            logger.error("Binary update failed (exit code %d).", result.returncode)
            sys.exit(result.returncode)
    finally:
        os.unlink(tmp_path)

    logger.info("Applying database migrations...")
    try:
        os.execv(binary_path, [binary_path, "migrate"])
    except OSError as exc:
        logger.error(
            "Failed to exec newly installed binary for migrations: %s\n"
            "Run migrations manually:  merakisync migrate",
            exc,
        )
        sys.exit(1)
