from __future__ import annotations

# PERSONAL_EXE_BUILD_V2

import argparse

from build_support import (
    build_personal,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "現在のCCFOLIA Managerと"
            "個人用app_dataをまとめて"
            "onedir EXEスナップショット化します。"
        )
    )

    parser.add_argument(
        "--include-exports",
        action="store_true",
        help=(
            "exportsフォルダも"
            "個人用スナップショットへ含める"
        ),
    )

    parser.add_argument(
        "--no-zip",
        action="store_true",
        help=(
            "フォルダだけ作り、"
            "ZIP圧縮を省略する"
        ),
    )

    parser.add_argument(
        "--output-dir",
        help=(
            "個人用ビルドの出力先。"
            "例: D:\\CCFOLIA_Manager_Self"
        ),
    )

    args = parser.parse_args()

    output = build_personal(
        include_exports=(
            args.include_exports
        ),
        make_zip_file=(
            not args.no_zip
        ),
        output_directory=(
            args.output_dir
        ),
    )

    print()
    print("Personal build: OK")
    print(f"folder: {output}")

    if not args.no_zip:
        print(
            "zip: "
            + str(
                output.with_suffix(
                    ".zip"
                )
            )
        )

    print()
    print(
        "この個人用版には現在の"
        "app_dataが含まれます。"
    )
    print(
        "第三者へ配布しないでください。"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
