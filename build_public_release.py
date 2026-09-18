from __future__ import annotations

# PUBLIC_EXE_BUILD_V1

import argparse

from build_support import (
    build_public,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "作者データを含まない"
            "CCFOLIA Manager配布版を"
            "onedir EXE + ZIPで作成します。"
        )
    )

    parser.add_argument(
        "--version",
        required=True,
        help="X.Y.Z 形式。例: 1.1.0",
    )

    args = parser.parse_args()

    folder, zip_path = build_public(
        version=args.version,
    )

    print()
    print("Public build: OK")
    print(f"folder: {folder}")
    print(f"zip:    {zip_path}")
    print()
    print(
        "app_data / backups / exports は"
        "配布版に含まれていません。"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
