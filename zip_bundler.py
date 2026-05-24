#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              ZIP → MARKDOWN CODEBASE BUNDLER  v3.0                         ║
║         Converts any ZIP project into a single AI-ready .md file           ║
║                  No sanitization. Full fidelity output.                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

HOW IT WORKS:
  1. Scans the repo root for any .zip file automatically
  2. Extracts it to a temp directory
  3. Walks every file, classifies text vs binary
  4. Writes a beautifully structured Markdown document
  5. Saves as project_codebase.md (ready for AI upload)

USAGE (local):
  python zip_bundler.py                    # auto-detect zip in current dir
  python zip_bundler.py myproject.zip      # explicit zip path
  python zip_bundler.py myzip.zip out.md   # custom output name
"""

import os
import sys
import zipfile
import tempfile
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone


# ═════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION — edit these if needed
# ═════════════════════════════════════════════════════════════════════════════

# Directories to skip entirely (no matter how deeply nested)
SKIP_DIRS = {
    ".git", ".github", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".tox", "dist", "build", ".next", ".nuxt", ".output",
    "out", "target", "bin", "obj", "venv", ".venv", "env", ".env",
    "vendor", "Pods", ".gradle", ".idea", ".vscode", ".DS_Store",
    "coverage", ".nyc_output", "storybook-static", ".angular",
    ".svelte-kit", ".turbo", "tmp", "temp", ".cache",
}

# File extensions treated as plain text (will be included in output)
TEXT_EXTENSIONS = {
    # ── Web ──────────────────────────────────────────────────────────────────
    ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".vue", ".svelte", ".astro", ".njk", ".ejs", ".pug", ".hbs",
    ".handlebars", ".mustache", ".jinja", ".jinja2", ".twig",
    # ── Config / Data ────────────────────────────────────────────────────────
    ".json", ".jsonc", ".json5", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".conf", ".config", ".properties", ".env", ".env.example",
    ".env.local", ".env.development", ".env.production", ".env.test",
    ".xml", ".plist", ".xsd", ".wsdl", ".dtd",
    # ── Documentation ────────────────────────────────────────────────────────
    ".md", ".mdx", ".rst", ".adoc", ".asciidoc", ".txt", ".text",
    ".tex", ".latex", ".org",
    # ── Backend / Systems ────────────────────────────────────────────────────
    ".py", ".pyw", ".pyi",
    ".java", ".kt", ".kts", ".groovy", ".scala", ".clj", ".cljs",
    ".cs", ".fs", ".fsx", ".vb",
    ".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx",
    ".go", ".rs", ".zig", ".nim",
    ".rb", ".rake", ".gemspec",
    ".php", ".phtml",
    ".swift", ".m", ".mm",
    ".r", ".rmd",
    ".lua", ".tcl", ".pl", ".pm", ".perl",
    ".asm", ".s",
    ".ex", ".exs",
    ".erl", ".hrl",
    ".hs", ".lhs",
    ".ml", ".mli",
    ".dart",
    ".jl",
    # ── Shell / Scripts ──────────────────────────────────────────────────────
    ".sh", ".bash", ".zsh", ".fish", ".ksh", ".csh",
    ".ps1", ".psm1", ".psd1",
    ".bat", ".cmd",
    # ── Database ─────────────────────────────────────────────────────────────
    ".sql", ".ddl", ".dml", ".prisma",
    # ── CI/CD / DevOps ───────────────────────────────────────────────────────
    ".dockerfile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".tf", ".tfvars", ".hcl",
    ".k8s", ".helm",
    # ── Build Tools ──────────────────────────────────────────────────────────
    ".gradle", ".maven", "Makefile", "makefile", "GNUmakefile",
    "Rakefile", "Gemfile", "Procfile", "Brewfile",
    ".lock",
    # ── Package Manager ──────────────────────────────────────────────────────
    ".npmrc", ".nvmrc", ".yarnrc", ".pnpmfile.cjs",
    ".ruby-version", ".python-version", ".node-version",
    # ── Linting / Formatting ─────────────────────────────────────────────────
    ".eslintrc", ".eslintignore", ".prettierrc", ".prettierignore",
    ".editorconfig", ".babelrc", ".browserslistrc",
    ".stylelintrc", ".pylintrc", ".flake8", ".ruff.toml",
    ".gitignore", ".dockerignore", ".npmignore",
    ".huskyrc", ".lintstagedrc",
    # ── GraphQL / API ────────────────────────────────────────────────────────
    ".graphql", ".gql", ".proto",
    # ── Cert / Key (text form) ───────────────────────────────────────────────
    ".pem", ".crt", ".cert", ".key", ".pub",
    # ── Misc ─────────────────────────────────────────────────────────────────
    ".csv", ".tsv", ".log", ".patch", ".diff",
    ".http", ".rest",
    ".tf", ".tfstate",
}

# Extensions that are definitely binary — skip content, list as asset
BINARY_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp",
    ".tiff", ".tif", ".avif", ".heic", ".heif", ".raw",
    # Vector (binary SVG variants)
    ".eps", ".ai", ".sketch", ".fig", ".xd",
    # Audio
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma", ".opus",
    # Video
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v",
    ".3gp", ".ogv",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".cab",
    ".iso", ".dmg", ".pkg", ".deb", ".rpm",
    # Documents
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".odt", ".ods", ".odp", ".rtf",
    # Fonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".fnt",
    # Executables / compiled
    ".exe", ".dll", ".so", ".dylib", ".app", ".apk", ".aab",
    ".ipa", ".msi", ".bin",
    # Build artifacts
    ".o", ".a", ".lib", ".class", ".jar", ".war", ".ear",
    ".pyc", ".pyo", ".pyd", ".npy", ".npz",
    # Databases
    ".db", ".sqlite", ".sqlite3", ".mdb",
    # Misc binary
    ".wasm", ".br", ".map",
}

# Language hint for markdown fenced code blocks
LANG_MAP = {
    ".py": "python", ".pyw": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "jsx", ".ts": "typescript", ".tsx": "tsx",
    ".html": "html", ".htm": "html", ".xhtml": "html",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".json": "json", ".jsonc": "json", ".json5": "json",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".xml": "xml", ".plist": "xml", ".xsd": "xml",
    ".md": "markdown", ".mdx": "markdown",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash",
    ".fish": "fish", ".ksh": "bash",
    ".ps1": "powershell", ".psm1": "powershell",
    ".bat": "batch", ".cmd": "batch",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala", ".groovy": "groovy",
    ".cs": "csharp", ".fs": "fsharp", ".vb": "vb",
    ".cpp": "cpp", ".cxx": "cpp", ".cc": "cpp",
    ".c": "c", ".h": "c", ".hpp": "cpp",
    ".go": "go", ".rs": "rust", ".zig": "zig",
    ".rb": "ruby", ".rake": "ruby",
    ".php": "php", ".phtml": "php",
    ".swift": "swift", ".m": "objectivec", ".mm": "objectivec",
    ".r": "r", ".rmd": "r",
    ".lua": "lua", ".pl": "perl", ".pm": "perl",
    ".ex": "elixir", ".exs": "elixir",
    ".erl": "erlang", ".hrl": "erlang",
    ".hs": "haskell", ".lhs": "haskell",
    ".ml": "ocaml", ".mli": "ocaml",
    ".dart": "dart", ".jl": "julia",
    ".sql": "sql", ".ddl": "sql", ".dml": "sql",
    ".graphql": "graphql", ".gql": "graphql",
    ".proto": "protobuf",
    ".tf": "hcl", ".tfvars": "hcl", ".hcl": "hcl",
    ".prisma": "prisma",
    ".vue": "vue", ".svelte": "svelte",
    ".dockerfile": "dockerfile",
    ".env": "bash",
    ".csv": "csv", ".tsv": "tsv",
    ".diff": "diff", ".patch": "diff",
    ".log": "log",
    ".txt": "text",
}

# Special filenames without extensions that are text
TEXT_FILENAMES = {
    "dockerfile", "makefile", "gnumakefile", "rakefile", "gemfile",
    "procfile", "brewfile", "vagrantfile", "jenkinsfile", "caddyfile",
    ".gitignore", ".dockerignore", ".npmignore", ".eslintignore",
    ".prettierignore", ".babelrc", ".nvmrc", ".npmrc", ".yarnrc",
    ".editorconfig", ".htaccess", ".env",
    "readme", "license", "licence", "changelog", "contributing",
    "authors", "contributors", "todo", "notes", "history",
    "copying", "credits", "install", "news",
}


# ═════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def find_zip_in_dir(directory: Path) -> Path | None:
    """Return the first .zip found in directory, or None."""
    zips = sorted(directory.glob("*.zip"))
    if not zips:
        return None
    if len(zips) > 1:
        print(f"[!] Multiple ZIPs found: {[z.name for z in zips]}")
        print(f"[→] Using: {zips[0].name}")
    return zips[0]


def should_skip_path(relative: Path) -> bool:
    """True if any part of the relative path is a skip-dir."""
    for part in relative.parts[:-1]:        # directories only (not filename)
        if part in SKIP_DIRS or part.startswith("."):
            return True
    return False


def classify_file(file_path: Path) -> str:
    """Return 'text', 'binary', or 'unknown'."""
    ext  = file_path.suffix.lower()
    name = file_path.name.lower()

    if ext in TEXT_EXTENSIONS or name in TEXT_FILENAMES:
        return "text"
    if ext in BINARY_EXTENSIONS:
        return "binary"

    # Sniff the first 8 KB
    try:
        with open(file_path, "rb") as fh:
            sample = fh.read(8192)
        if not sample:
            return "text"
        if b"\x00" in sample:
            return "binary"
        # Ratio of non-ASCII bytes
        non_ascii = sum(1 for b in sample if b > 127)
        if non_ascii / len(sample) > 0.30:
            return "binary"
        return "text"
    except OSError:
        return "unknown"


def file_md5(file_path: Path) -> str:
    """Return a short MD5 hex for the file."""
    h = hashlib.md5()
    try:
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:8]
    except OSError:
        return "????????"


def lang_hint(file_path: Path) -> str:
    """Return the markdown fenced-block language identifier."""
    ext  = file_path.suffix.lower()
    name = file_path.name.lower()
    if ext in LANG_MAP:
        return LANG_MAP[ext]
    if "dockerfile" in name:
        return "dockerfile"
    if name in ("makefile", "gnumakefile", "rakefile"):
        return "makefile"
    return ""


def human_size(n_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n_bytes < 1024:
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f} TB"


def count_lines(text: str) -> int:
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


# ═════════════════════════════════════════════════════════════════════════════
#  CORE BUNDLER
# ═════════════════════════════════════════════════════════════════════════════

def bundle(zip_path: Path, output_path: Path, verbose: bool = True) -> bool:
    """
    Main entry point.
    Extracts zip_path → temp dir → walks files → writes output_path.
    Returns True on success.
    """
    if not zip_path.exists():
        print(f"[✗] ZIP not found: {zip_path}")
        return False

    zip_size   = zip_path.stat().st_size
    started_at = datetime.now(timezone.utc)

    if verbose:
        print()
        print("━" * 70)
        print("  ZIP → MARKDOWN BUNDLER  v3.0")
        print("━" * 70)
        print(f"  ZIP     : {zip_path.name}  ({human_size(zip_size)})")
        print(f"  Output  : {output_path.name}")
        print(f"  Started : {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("━" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # ── 1. Extract ──────────────────────────────────────────────────────
        if verbose:
            print("[1/4] Extracting ZIP …")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Safety: strip any absolute paths
                for member in zf.infolist():
                    target = tmp_path / member.filename
                    # Prevent path traversal
                    if not str(target.resolve()).startswith(str(tmp_path.resolve())):
                        if verbose:
                            print(f"      [SKIP – path traversal] {member.filename}")
                        continue
                    zf.extract(member, tmp_path)
        except zipfile.BadZipFile as exc:
            print(f"[✗] Bad ZIP file: {exc}")
            return False

        # ── 2. Walk & classify ──────────────────────────────────────────────
        if verbose:
            print("[2/4] Scanning files …")

        text_files   = []   # list of (relative_path, absolute_path)
        binary_files = []   # list of relative_path strings
        skipped      = []   # list of relative_path strings (skip-dir)

        for abs_path in sorted(tmp_path.rglob("*")):
            if not abs_path.is_file():
                continue

            rel = abs_path.relative_to(tmp_path)

            if should_skip_path(rel):
                skipped.append(str(rel))
                continue

            kind = classify_file(abs_path)
            if kind == "text":
                text_files.append((rel, abs_path))
            else:
                binary_files.append(str(rel))

        if verbose:
            print(f"      Text   : {len(text_files):>5} files")
            print(f"      Binary : {len(binary_files):>5} files")
            print(f"      Skipped: {len(skipped):>5} files (excluded dirs)")

        # ── 3. Build Markdown ───────────────────────────────────────────────
        if verbose:
            print("[3/4] Building Markdown document …")

        lines = []
        total_code_lines  = 0
        total_code_bytes  = 0
        file_tree_entries = []

        # ─── Document Header ────────────────────────────────────────────────
        lines.append(f"# 📦 Codebase Bundle")
        lines.append(f"")
        lines.append(f"> **Source ZIP**: `{zip_path.name}`  ")
        lines.append(f"> **Generated** : {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
        lines.append(f"> **Text files**: {len(text_files)}  |  "
                     f"**Binary assets**: {len(binary_files)}  |  "
                     f"**ZIP size**: {human_size(zip_size)}")
        lines.append(f"")
        lines.append("---")
        lines.append("")

        # ─── Table of Contents ──────────────────────────────────────────────
        lines.append("## 📋 Table of Contents")
        lines.append("")
        lines.append("1. [📊 Project Statistics](#-project-statistics)")
        lines.append("2. [🗂️ File Tree](#️-file-tree)")
        lines.append("3. [🖼️ Binary & Media Assets](#️-binary--media-assets)")
        lines.append("4. [💻 Source Code Files](#-source-code-files)")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ─── Project Statistics (placeholder, filled after loop) ────────────
        stats_index = len(lines)   # remember position
        lines.append("__STATS_PLACEHOLDER__")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ─── File Tree ──────────────────────────────────────────────────────
        lines.append("## 🗂️ File Tree")
        lines.append("")
        lines.append("```")
        # Build tree from text + binary file paths
        all_paths = sorted(
            [str(r) for r, _ in text_files] + binary_files
        )
        for p in all_paths:
            depth = p.count(os.sep) + p.count("/")
            indent = "  " * depth
            fname  = Path(p).name
            lines.append(f"{indent}{'├── ' if depth else ''}{fname}")
            file_tree_entries.append(p)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ─── Binary Assets ──────────────────────────────────────────────────
        lines.append("## 🖼️ Binary & Media Assets")
        lines.append("")
        if binary_files:
            lines.append("These files are part of the project but contain binary data "
                         "and are listed here for reference only:")
            lines.append("")
            lines.append("| # | File | Extension |")
            lines.append("|---|------|-----------|")
            for idx, bf in enumerate(sorted(binary_files), 1):
                ext = Path(bf).suffix or "(none)"
                lines.append(f"| {idx} | `{bf}` | `{ext}` |")
        else:
            lines.append("_No binary or media files found in this project._")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ─── Source Code ────────────────────────────────────────────────────
        lines.append("## 💻 Source Code Files")
        lines.append("")

        for idx, (rel, abs_path) in enumerate(text_files, 1):
            file_size  = abs_path.stat().st_size
            checksum   = file_md5(abs_path)
            lang       = lang_hint(abs_path)
            ext        = abs_path.suffix or "(no ext)"

            # Read content — raw, unmodified
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                content = f"[ERROR READING FILE: {exc}]"

            n_lines = count_lines(content)
            total_code_lines += n_lines
            total_code_bytes += file_size

            if verbose and idx % 30 == 0:
                print(f"      … processed {idx}/{len(text_files)} files")

            # Section heading
            lines.append(f"### [{idx}/{len(text_files)}] `{rel}`")
            lines.append(f"")
            lines.append(f"| Property | Value |")
            lines.append(f"|----------|-------|")
            lines.append(f"| **Path** | `{rel}` |")
            lines.append(f"| **Type** | `{ext}` |")
            lines.append(f"| **Size** | {human_size(file_size)} |")
            lines.append(f"| **Lines** | {n_lines:,} |")
            lines.append(f"| **MD5 (short)** | `{checksum}` |")
            lines.append(f"")

            # Code block
            lines.append(f"```{lang}")
            lines.append(content if content.endswith("\n") else content + "\n")
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        # ─── Fill statistics placeholder ────────────────────────────────────
        finished_at    = datetime.now(timezone.utc)
        duration_secs  = (finished_at - started_at).total_seconds()
        total_lines_md = len(lines)
        md_text        = "\n".join(lines)
        md_bytes       = len(md_text.encode("utf-8"))

        stats_block = [
            "## 📊 Project Statistics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Source ZIP | `{zip_path.name}` |",
            f"| ZIP File Size | {human_size(zip_size)} |",
            f"| Text Files Bundled | {len(text_files):,} |",
            f"| Binary Files Listed | {len(binary_files):,} |",
            f"| Excluded (skip dirs) | {len(skipped):,} |",
            f"| Total Source Lines | {total_code_lines:,} |",
            f"| Total Source Size | {human_size(total_code_bytes)} |",
            f"| Output .md Size | {human_size(md_bytes)} |",
            f"| Output .md Lines | {total_lines_md:,} |",
            f"| Generated At | {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')} |",
            f"| Processing Time | {duration_secs:.2f}s |",
        ]
        lines[stats_index] = "\n".join(stats_block)

        # Rebuild final text with stats filled
        md_text = "\n".join(lines)

        # ── 4. Write output ─────────────────────────────────────────────────
        if verbose:
            print("[4/4] Writing output file …")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_text, encoding="utf-8")

        final_size = output_path.stat().st_size

        if verbose:
            print()
            print("━" * 70)
            print("  ✅  DONE!")
            print("━" * 70)
            print(f"  Output file   : {output_path}")
            print(f"  Output size   : {human_size(final_size)}")
            print(f"  Source lines  : {total_code_lines:,}")
            print(f"  Text files    : {len(text_files):,}")
            print(f"  Binary assets : {len(binary_files):,}")
            print(f"  Time taken    : {duration_secs:.2f}s")
            print("━" * 70)
            print()

        return True


# ═════════════════════════════════════════════════════════════════════════════
#  CLI
# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="zip_bundler",
        description="Convert a ZIP project into a single AI-ready Markdown file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES
  python zip_bundler.py                    # auto-detect .zip in current dir
  python zip_bundler.py myapp.zip          # explicit zip
  python zip_bundler.py myapp.zip out.md   # custom output name
  python zip_bundler.py -q myapp.zip       # quiet mode (no console output)
        """,
    )
    parser.add_argument(
        "zip_file",
        nargs="?",
        default=None,
        help="Path to the .zip file (auto-detected if omitted)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="project_codebase.md",
        help="Output .md filename (default: project_codebase.md)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all console output",
    )

    args = parser.parse_args()

    # Resolve zip path
    if args.zip_file:
        zip_path = Path(args.zip_file)
    else:
        zip_path = find_zip_in_dir(Path("."))
        if zip_path is None:
            print("[✗] No .zip file found in the current directory.")
            print("    Pass the zip path as an argument:  python zip_bundler.py myapp.zip")
            return 1

    output_path = Path(args.output)
    ok = bundle(zip_path, output_path, verbose=not args.quiet)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
