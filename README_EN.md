<div align="center">
  <img src="pure-code/icons/icon.png" alt="PureCode Logo" width="128" height="128">
  <h1>PureCode</h1>
  <p><strong>Strip comments · Arrange file order · Export copyright-ready code documents</strong></p>
  <p>
    <img src="https://img.shields.io/badge/version-release.1.0.0-blue" alt="version">
    <img src="https://img.shields.io/badge/license-AGPL--3.0-green" alt="license">
    <img src="https://img.shields.io/badge/platform-InstructionX-orange" alt="platform">
  </p>
  <p><a href="README.md">中文</a> | English</p>
</div>

## Introduction

When applying for **software copyright registration** in China, the copyright office requires a Word document containing your source code — with **all comments removed**, keeping only the code itself. And when the filing is handled by a third-party agency, you usually **cannot control which source files appear first** in the document.

**PureCode** is a plugin for the [InstructionX](https://github.com/KKPIP-Tech/InstructionX) framework, built to solve exactly these two pain points:

1. **Comment stripping**: an extensible, rule-based engine accurately removes line comments, block comments and docstrings (e.g. Python `"""` docstrings) — **without ever modifying your source files**;
2. **File ordering**: drag and drop to freely arrange the order in which files appear in the exported document, putting your core code up front.

The result is a one-click `{project name}_code.docx` document, ready for copyright application materials.

## Features

![Main Window](pure-code/docs/images/main_window.png)

- **Project scanning**: pick a project directory and all files are scanned recursively, displayed hierarchically in a Tree view;
- **Coarse file-type filter**: after scanning, all detected file extensions are listed as checkboxes for quick filtering;
- **Fine-grained file selection**: check individual files or whole directories in the Tree to decide exactly what goes into the document;
- **Comment-stripping engine**: 9 built-in language rules (Python, C, C++, C#, Java, JavaScript, TypeScript, Go, Rust); string-literal aware, so `//` or `#` inside strings is never touched;
- **File ordering**: reorder files by dragging or with buttons; custom order takes precedence over default path sorting;
- **Export progress feedback**: a progress bar tracks both phases (per-file processing → document writing) while the processing log scrolls alongside;
- **Bilingual UI**: Chinese / English, switching live with the framework language;
- **Cross-plugin / MCP API**: exposes an `export_code_document` service for headless invocation.

### Coarse File-Type Filter

After scanning, a dialog groups files by extension with counts, supporting select-all / clear:

![File Type Dialog](pure-code/docs/images/file_type_dialog.png)

### File Ordering

![File Order Dialog](pure-code/docs/images/sort_dialog.png)

### Language Settings (Extensible Rules)

The language settings window has two columns: a language list with an "Add Language" button on the left, and the selected language's comment rules and file extensions on the right. Built-in rules can be saved as custom copies, or you can create a brand-new language from scratch:

![Language Settings Dialog](pure-code/docs/images/language_dialog.png)

## Installation

The PureCode repository is a standard InstructionX single-plugin repository (with `IXRepo.json` at its root), installed via the framework's built-in one-click GitHub installer:

1. Open InstructionX and go to the "Plugin Management" dialog;
2. Choose "Install from GitHub" and paste the repository URL:

   ```
   https://github.com/Ender-William/PureCode.git
   ```

3. Confirm the installation. The declared `python-docx (>=1.1.0)` dependency is installed automatically by the framework — no manual steps needed.

## Usage

1. **Select a project directory**: click "Select Project Directory" on the toolbar and pick the project root;
2. **Coarse-filter file types**: in the dialog that pops up, check the extensions to include;
3. **Fine-tune the selection**: check exactly the files you want in the file tree on the left;
4. **Arrange the order (optional)**: click "Arrange File Order" and drag files into place; in the settings panel on the right you can toggle "Remove blank lines" and "Keep files without a matching rule as-is";
5. **Export**: click "Start Export", confirm the save path (default file name `{project name}_code.docx`), and wait for the progress bar to finish.

## Custom Language Rules

Rules added or edited in the language settings are persisted as JSON objects with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Language name (required, unique) |
| `extensions` | string[] | Associated file extensions (required; normalized to lowercase with a leading dot) |
| `line_comments` | string[] | Line comment tokens, e.g. `//`, `#` (at least one of line/block comments required) |
| `block_comments` | [string, string][] | Block comment start/end pairs, e.g. `["/*", "*/"]` |
| `string_delimiters` | string[] | String delimiters, e.g. `"`, `'` (protects string contents from stripping) |
| `docstrings` | string[] | Docstring delimiters, e.g. `"""` (stripped via a line-start heuristic) |
| `escape_char` | string | String escape character, defaults to `\` |
| `nested_block` | bool | Whether block comments can nest (e.g. Rust), defaults to `false` |

Custom rules are stored in the plugin's private data area (DataProvider) and persist with framework data — reinstalling the plugin does not lose them.

## The Exported Document

- **File name**: `{project name}_code.docx` by default (the project name is the selected directory's name);
- **Layout**: A4 pages with the project name as the document title;
- **File blocks**: each file appears under its relative path as a heading, followed by its comment-free code in Consolas monospace;
- **Source safety**: all stripping happens in memory — **no source file is ever written back or modified**.

## Known Limitations

- Python docstrings are stripped via a **line-start heuristic** (`"""`/`'''` at the start of a line, preceded only by indentation, is treated as a doc comment); the trade-off is that bare triple-quoted string expressions at line start are stripped as well (lexically indistinguishable from docstrings), while multi-line strings in assignment/argument positions are unaffected;
- Custom file order lives in memory only and resets when a new directory is selected;
- No automatic page/line trimming for copyright templates (e.g. "first 60 pages"); the document contains the full code of all checked files.

## Public API

The plugin exposes a service via `service_api` (automatically registered as a cross-plugin API and synced as an MCP tool):

```python
export_code_document(
    project_dir: str,                 # project directory
    output_path: str,                 # output .docx path
    extensions: list[str] | None,     # restrict to extensions; None means all
    remove_blank_lines: bool = False, # strip blank lines
) -> dict  # {output_path, file_count, skipped, unmatched}
```

## Development & Testing

- Branch convention: `dev` is a pure development branch; pytest test code lives only on the `test` branch;
- Run tests from the framework repository root (on a branch that contains the test code):

  ```powershell
  .venv\Scripts\python.exe -m pytest custom_plugin/test/ -q
  ```

- Requirements and design documents (Chinese): `pure-code/docs/req/2026-09-07/` (PRD / SPEC).

## License

This project is open-sourced under [GNU AGPL v3](LICENSE).

**Author**: William_Kuang
