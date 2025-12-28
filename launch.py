#!/usr/bin/env python3
"""Cross-platform launcher for xobliam dashboard."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Launch the xobliam Streamlit dashboard."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent.absolute()
    app_path = script_dir / "xobliam" / "app.py"

    if not app_path.exists():
        print(f"Error: Could not find {app_path}")
        sys.exit(1)

    # Change to the project directory
    os.chdir(script_dir)

    print()
    print("=" * 40)
    print("  xobliam - Gmail Analytics Dashboard")
    print("=" * 40)
    print()
    print("Starting dashboard...")
    print("The dashboard will open in your browser.")
    print("Press Ctrl+C to stop the server.")
    print()

    try:
        # Run streamlit
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                "--server.headless",
                "true",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    except subprocess.CalledProcessError as e:
        print(f"Error running streamlit: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: Streamlit is not installed.")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
