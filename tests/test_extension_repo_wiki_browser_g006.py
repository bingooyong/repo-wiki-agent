"""G006 VS Code/Cursor READY-release browser security and metadata tests."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = REPO_ROOT / "extensions" / "repo-wiki-browser"
PACKAGE_JSON = EXT_DIR / "package.json"
EXTENSION_TS = EXT_DIR / "src" / "extension.ts"


def _source() -> str:
    return EXTENSION_TS.read_text()


def test_ready_page_resolution_is_content_root_only_and_escape_checked() -> None:
    source = _source()

    assert "const RELEASE_CONTENT_DIR = 'content';" in source
    assert "const contentDirCandidate = path.join(run.manifestDir, RELEASE_CONTENT_DIR);" in source
    assert (
        "resolveExistingDirectoryInside(workspaceRoot, contentDirCandidate, run.manifestDir)"
        in source
    )
    assert (
        "safeResolveReleasePagePath(contentDir, node.path, workspaceRoot, releaseRoot, manifestPath)"
        in source
    )
    assert "node.absolutePath ? path.resolve(node.absolutePath)" not in source

    helper = re.search(
        r"export function safeResolveReleasePagePath[\s\S]+?\n}\n\nfunction normalizeReleasePageRelativePath",
        source,
    )
    assert helper is not None
    body = helper.group(0)
    assert "path.isAbsolute(normalizedInput)" in body
    assert "normalizedInput.split('/').includes('..')" in body
    assert "isPathInside(absolutePath, contentRoot)" in body
    assert "fs.realpathSync(contentRoot)" in body
    assert "fs.realpathSync(absolutePath)" in body
    assert "fs.realpathSync(workspaceRoot)" in body
    assert "fs.realpathSync(releaseRoot)" in body
    assert "fs.realpathSync(manifestPath)" in body
    assert "fs.statSync(absolutePath)" in body
    assert "!stat.isFile()" in body
    assert "path.extname(relativePath).toLowerCase() !== '.md'" in body


def test_open_page_command_uses_release_page_id_not_arbitrary_absolute_path() -> None:
    source = _source()

    assert (
        "registerCommand('repoWikiBrowser.openPage', (pageIdOrPath: unknown) => sidebarProvider.openPageCommand(pageIdOrPath))"
        in source
    )
    command = re.search(r"openPageCommand\(pageIdOrPath: unknown\): void \{[\s\S]+?\n    }", source)
    assert command is not None
    body = command.group(0)
    assert "this.fileById.get(id)" in body
    assert "Rejected Wiki page request outside the published READY release" in body
    assert (
        "safeResolveReleasePagePath(source.contentDir, file.relativePath, source.workspaceRoot, source.manifestDir, source.manifestPath)"
        in body
    )
    assert "openMarkdownPreview(refreshed.absolutePath)" in body


def test_source_citation_command_rejects_escapes_and_supports_structured_and_legacy_forms() -> None:
    manifest = json.loads(PACKAGE_JSON.read_text())
    assert "onCommand:repoWikiBrowser.openSourceCitation" in manifest["activationEvents"]
    assert any(
        c["command"] == "repoWikiBrowser.openSourceCitation"
        for c in manifest["contributes"]["commands"]
    )

    source = _source()
    assert "repoWikiBrowser.openSourceCitation" in source
    assert "export function parseSourceCitation" in source
    assert "parseLegacySourceCitation" in source
    assert "pickString(obj.source_path)" in source
    assert "pickString(obj.sourcePath)" in source
    assert "pickString(obj.path)" in source
    assert "normalizeWorkspaceRelativePath" in source
    assert "path.isAbsolute(normalized)" in source
    assert "normalized.split('/').includes('..')" in source
    assert "resolveWorkspaceSourcePath" in source
    assert "fs.realpathSync(workspaceRoot)" in source
    assert "clampLine(parsed.startLine ?? 1, lineCount)" in source
    assert "new vscode.Selection(anchor, startCharacter, active, endCharacter)" in source


def test_ready_sidecars_drive_related_and_impacted_pages_without_run_dir_fallback() -> None:
    source = _source()

    assert "const metaDir = path.join(run.manifestDir, RELEASE_META_DIR);" in source
    assert (
        "loadEvidenceIndex(workspaceRoot, run.manifestDir, path.join(metaDir, 'evidence-index.json'))"
        in source
    )
    assert (
        "loadPageRegistry(workspaceRoot, run.manifestDir, path.join(metaDir, 'page-registry.json'))"
        in source
    )
    assert (
        "readReleaseSidecarObject(workspaceRoot, run.manifestDir, path.join(metaDir, 'release.json'))"
        in source
    )
    assert "buildRelatedPagesBySource(files, evidenceIndex, pageRegistry)" in source
    assert "source.relatedPagesBySource.get(sourcePath)" in source
    assert "fileId: file.id" in source
    assert "startLine: span.startLine" in source
    assert "endLine: span.endLine" in source
    assert "citations: [citation]" in source
    assert "existing.citations.length < 3" in source
    assert "page.citations.slice(0, 3)" in source
    assert "data-citation-id" in source
    assert "openSourceCitation', citation" in source
    assert "getActiveSourceRelatedPages(source)" in source
    assert "collectRelatedPagesForSources(source, changedFilePaths)" in source
    assert "discoverRun" not in source
    assert "path.join(workspaceRoot, 'docs')" not in source


def test_sidebar_renders_explicit_ready_release_source_run_publish_commit_provenance() -> None:
    source = _source()

    assert "function renderReleaseProvenance" in source
    assert "READY" in source
    assert "Release" in source
    assert "Source run" in source
    assert "Published" in source
    assert "Commit" in source
    assert "FreshnessState = 'fresh' | 'stale' | 'unknown'" in source
    assert "gitStatus.freshness === 'stale' ? 'STALE'" in source
    assert "gitStatus.freshness === 'fresh' ? 'fresh' : 'UNKNOWN'" in source


def test_git_freshness_uses_target_or_wiki_baseline_and_unknown_when_missing() -> None:
    source = _source()

    status = re.search(
        r"function getGitStatus\(workspaceRoot: string, source: WikiSource\): GitStatus \{[\s\S]+?\n\}\n\nfunction findCommitInObject",
        source,
    )
    assert status is not None
    body = status.group(0)
    assert "const baselineCommit = source.targetGitCommit ?? wikiCommit;" in body
    assert "if (!wikiCommit)" not in body
    assert "if (!currentCommit)" in body
    assert "if (!baselineCommit)" in body
    assert body.count("freshness: 'unknown'") == 2
    assert (
        "currentCommit.startsWith(baselineCommit) || baselineCommit.startsWith(currentCommit)"
        in body
    )
    assert "freshness: 'fresh'" in body
    assert "listChangedFiles(workspaceRoot, baselineCommit, currentCommit)" in body
    assert "freshness: 'stale'" in body


def test_release_manifest_content_and_sidecars_are_realpath_contained() -> None:
    source = _source()

    assert "resolveExistingDirectoryInside(workspaceRoot, releaseRootCandidate)" in source
    assert (
        "resolveExistingFileInside(workspaceRoot, releaseRoot, path.join(releaseRoot, 'manifest.json'))"
        in source
    )
    assert "readReleaseSidecarObject(workspaceRoot, releaseRoot, manifestPath)" in source
    assert "resolveExistingFileInside(workspaceRoot, releaseRoot, filePath)" in source
    assert (
        "!isPathInside(realFile, realWorkspace) || !isPathInside(realFile, realReleaseRoot)"
        in source
    )
    assert "const parsed = JSON.parse(raw) as unknown;" in source


def test_release_metadata_json_parser_is_strict_and_rejects_jsonc_tolerance() -> None:
    source = _source()

    parser = re.search(
        r"function readJsonObject\(filePath: string\): Record<string, unknown> \| undefined \{[\s\S]+?\n\}\n",
        source,
    )
    assert parser is not None
    body = parser.group(0)
    assert "JSON.parse(raw)" in body
    assert "tolerantParseJson" not in source
    assert "withoutComments" not in source
    assert "withoutTrailingCommas" not in source
    assert "strip-json-comments" not in source
    assert ".replace(/\\/\\*" not in source
    assert ".replace(/,\\s*([}\\]])" not in source


def test_strict_json_parse_rejects_release_metadata_comments_and_trailing_commas() -> None:
    if shutil.which("node") is None:
        return

    script = r"""
const malformedReleaseMetadata = [
  '{"release_status":"READY",// comment\n"navigation_tree":[]}',
  '{/* comment */"release_status":"READY","navigation_tree":[]}',
  '{"release_status":"READY","navigation_tree":[],}',
  '{"release_status":"READY","navigation_tree":[{"type":"page",}],}'
];
for (const raw of malformedReleaseMetadata) {
  try {
    JSON.parse(raw);
    process.exit(1);
  } catch {
    // Strict JSON.parse rejects comments and trailing commas.
  }
}
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_active_editor_refresh_and_webview_delegation_are_wired() -> None:
    source = _source()

    assert "vscode.window.onDidChangeActiveTextEditor(() => sidebarProvider.refresh())" in source
    assert "target.closest('[data-id]')" in source
    assert "target.closest('[data-citation-id]')" in source
    assert "JSON.parse(citationMapElement.textContent || '{}')" in source
    assert "safeJsonForInline(citationData)" in source
