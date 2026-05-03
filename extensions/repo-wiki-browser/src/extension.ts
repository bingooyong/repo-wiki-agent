import * as childProcess from 'child_process';
import * as fs from 'fs';
import yaml from 'js-yaml';
import * as path from 'path';
import * as vscode from 'vscode';

const DEFAULT_GENERATE_COMMAND = 'uv run repo-wiki generate --profile qoder-like';

type WikiNodeType = 'overview' | 'section' | 'module' | 'api' | 'data' | 'operations' | 'development' | 'security' | 'other';

interface WikiFile {
    id: string;
    label: string;
    relativePath: string;
    absolutePath: string;
    type: WikiNodeType;
}

interface WikiGroup {
    label: string;
    children: WikiFile[];
}

interface WikiSource {
    manifestPath: string;
    manifestDir: string;
    runKey: string;
    runLabel: string;
    label: string;
    availableRuns: ManifestRunSummary[];
    files: WikiFile[];
    manifest: Record<string, unknown>;
    navigationTree: NavigationTreeNode[];
    wikiGitCommit?: string;
    targetGitCommit?: string;
}

interface ManifestRunSummary {
    key: string;
    label: string;
    manifestPath: string;
    manifestDir: string;
    mtimeMs: number;
    generatedAt?: string;
}

interface NavigationTreeNode {
    type?: string;
    label?: string;
    id?: string;
    path?: string;
    absolutePath?: string;
    children?: NavigationTreeNode[];
}

interface GitStatus {
    currentCommit?: string;
    wikiCommit?: string;
    changedFiles?: number;
    isStale: boolean;
    message: string;
}

interface LlmDisplayInfo {
    configFound: boolean;
    configFile?: string;
    parseError?: boolean;
    provider?: string;
    modelInit?: string;
    modelUpdate?: string;
    modelVerify?: string;
    flatModel?: string;
}

let sidebarProvider: RepoWikiSidebarProvider;

export function activate(context: vscode.ExtensionContext) {
    sidebarProvider = new RepoWikiSidebarProvider(context.extensionUri);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('repoWikiBrowser.sidebar', sidebarProvider),
        vscode.commands.registerCommand('repoWikiBrowser.openViewer', () => sidebarProvider.openDefaultPage()),
        vscode.commands.registerCommand('repoWikiBrowser.refreshTree', () => sidebarProvider.refresh()),
        vscode.commands.registerCommand('repoWikiBrowser.runVerify', () => runTerminalCommand('Repo Wiki Verify', 'repo-wiki verify --ci')),
        vscode.commands.registerCommand('repoWikiBrowser.updateWiki', () => runUpdateWiki()),
        vscode.commands.registerCommand('repoWikiBrowser.syncWiki', () => runTerminalCommand('Repo Wiki Sync', 'repo-wiki sync')),
        vscode.commands.registerCommand('repoWikiBrowser.openPage', (absolutePath: string) => openMarkdownPreview(absolutePath)),
        vscode.workspace.onDidChangeConfiguration((e) => {
            if (e.affectsConfiguration('repoWikiBrowser')) {
                sidebarProvider.refresh();
            }
        })
    );
}

export function deactivate() {}

class RepoWikiSidebarProvider implements vscode.WebviewViewProvider {
    private view?: vscode.WebviewView;
    private source?: WikiSource;
    private fileById = new Map<string, WikiFile>();
    private locale = 'zh-CN';
    private selectedRunKey?: string;

    constructor(private readonly extensionUri: vscode.Uri) {}

    resolveWebviewView(webviewView: vscode.WebviewView): void {
        this.view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.extensionUri],
        };

        webviewView.webview.onDidReceiveMessage((message) => {
            switch (message.command) {
                case 'openPage': {
                    const file = this.fileById.get(String(message.id));
                    if (file) {
                        openMarkdownPreview(file.absolutePath);
                    }
                    break;
                }
                case 'refresh':
                    this.refresh();
                    break;
                case 'update':
                    runUpdateWiki();
                    break;
                case 'sync':
                    runTerminalCommand('Repo Wiki Sync', 'repo-wiki sync');
                    break;
                case 'locale':
                    this.locale = String(message.locale || 'zh-CN');
                    this.refresh();
                    break;
                case 'selectRun':
                    this.selectedRunKey = String(message.runKey || '');
                    this.refresh();
                    break;
            }
        });

        this.refresh();
    }

    refresh(): void {
        const workspaceRoot = getWorkspaceRoot();
        if (!this.view) {
            return;
        }

        if (!workspaceRoot) {
            this.view.webview.html = this.renderNoWorkspace();
            return;
        }

        this.source = discoverWikiSource(workspaceRoot, this.selectedRunKey);
        this.selectedRunKey = this.source?.runKey;
        this.fileById.clear();
        if (this.source) {
            for (const file of this.source.files) {
                this.fileById.set(file.id, file);
            }
        }

        if (!this.source) {
            this.view.webview.html = this.renderNoWikiRuns(workspaceRoot);
            return;
        }

        const gitStatus = getGitStatus(workspaceRoot, this.source);
        const llmInfo = loadLlmDisplayInfo(workspaceRoot);
        this.view.webview.html = this.renderSidebar(this.source, gitStatus, llmInfo);
    }

    openDefaultPage(): void {
        const workspaceRoot = getWorkspaceRoot();
        if (!workspaceRoot) {
            vscode.window.showWarningMessage('No workspace folder open');
            return;
        }

        const source = this.source ?? discoverWikiSource(workspaceRoot, this.selectedRunKey);
        const defaultFile = source?.files.find((file) => file.relativePath.endsWith('00-overview.md')) ?? source?.files[0];
        if (!defaultFile) {
            vscode.window.showInformationMessage('No wiki content found. Run "Repo Wiki: Update Wiki" first.');
            return;
        }
        openMarkdownPreview(defaultFile.absolutePath);
    }

    private renderNoWorkspace(): string {
        return baseHtml(`
            <section class="panel">
                <h1>REPO WIKI</h1>
                <p class="muted">Open a repository workspace to browse wiki content.</p>
            </section>
        `);
    }

    private renderNoWikiRuns(workspaceRoot: string): string {
        const releaseManifestPath = path.join(workspaceRoot, '.repo-agent-eval', 'repowiki', 'zh', 'manifest.json');
        return baseHtml(`
            <section class="panel">
                <h1>REPO WIKI</h1>
                <p class="muted">未检测到已发布的 READY Wiki。</p>
                <p class="muted">请先发布：<code>.repo-agent-eval/repowiki/zh/manifest.json</code></p>
                <p class="muted">插件只读取 release manifest 的 <code>navigation_tree</code>，不回退扫描 run 目录或 <code>docs/</code>。</p>
                <p class="muted">查找文件：<code>${escapeHtml(releaseManifestPath)}</code></p>
                <div class="actions">
                    <button class="primary" data-command="update">更新 Wiki</button>
                    <button data-command="sync">同步</button>
                    <button class="icon" title="刷新" data-command="refresh">↻</button>
                </div>
            </section>
        `);
    }

    private renderSidebar(source: WikiSource, gitStatus: GitStatus, llmInfo: LlmDisplayInfo): string {
        const treeHtml = source.navigationTree.length > 0
            ? renderNavigationTree(source.navigationTree, source.files)
            : '<p class="muted">No navigation_tree found in manifest.</p>';

        const statusClass = gitStatus.isStale ? 'notice stale' : 'notice';
        const updateButton = gitStatus.isStale
            ? '<button class="primary" data-command="update">更新</button>'
            : '<button class="primary" data-command="update">更新 Wiki</button>';

        const llmPanel = renderLlmPanel(llmInfo, this.locale);
        const runOptions = source.availableRuns
            .map((run) => `<option value="${escapeHtml(run.key)}" ${run.key === source.runKey ? 'selected' : ''}>${escapeHtml(run.label)}</option>`)
            .join('');

        return baseHtml(`
            <header class="topbar">
                <div class="brand">REPO WIKI</div>
                <select id="locale" aria-label="Language">
                    <option value="zh-CN" ${this.locale === 'zh-CN' ? 'selected' : ''}>简体中文</option>
                    <option value="en" ${this.locale === 'en' ? 'selected' : ''}>English</option>
                </select>
            </header>

            ${llmPanel}

            <section class="run-panel">
                <div class="run-panel-title">Release</div>
                <select id="runSelect" aria-label="Wiki Run">
                    ${runOptions}
                </select>
                <p class="muted run-meta">${escapeHtml(source.label)}</p>
            </section>

            <section class="${statusClass}">
                <p>${escapeHtml(gitStatus.message)}</p>
                <div class="actions">
                    ${updateButton}
                    <button data-command="sync">同步</button>
                    <button class="icon" title="刷新" data-command="refresh">↻</button>
                </div>
            </section>

            <nav class="tree" aria-label="Repo Wiki navigation">
                ${treeHtml}
            </nav>
        `);
    }
}

function pickString(value: unknown): string | undefined {
    return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined;
}

function loadLlmDisplayInfo(workspaceRoot: string): LlmDisplayInfo {
    const candidates = ['repo-wiki.yaml', '.repo-wiki.yaml'];
    for (const name of candidates) {
        const fullPath = path.join(workspaceRoot, name);
        if (!fs.existsSync(fullPath)) {
            continue;
        }
        try {
            const raw = fs.readFileSync(fullPath, 'utf8');
            const doc = yaml.load(raw) as unknown;
            if (!doc || typeof doc !== 'object') {
                return { configFound: false, configFile: name, parseError: true };
            }
            const rootObj = doc as Record<string, unknown>;
            const llmRaw = rootObj.llm;
            const llmObj =
                llmRaw && typeof llmRaw === 'object' && llmRaw !== null
                    ? (llmRaw as Record<string, unknown>)
                    : {};
            return {
                configFound: true,
                configFile: name,
                provider: pickString(llmObj.provider),
                modelInit: pickString(llmObj.model_init),
                modelUpdate: pickString(llmObj.model_update),
                modelVerify: pickString(llmObj.model_verify),
                flatModel: pickString(llmObj.model),
            };
        } catch {
            return { configFound: false, configFile: name, parseError: true };
        }
    }
    return { configFound: false };
}

function cliEnvironmentFootnote(locale: string): string {
    const en = locale === 'en';
    const text = en
        ? 'Generate runs in the integrated terminal; uv and repo-wiki must resolve there. This extension does not bundle the Python CLI.'
        : '生成命令在集成终端执行，该环境中需能解析 uv 与 repo-wiki；扩展不内置 Python CLI。';
    return `<p class="muted llm-hint">${escapeHtml(text)}</p>`;
}

function renderLlmPanel(info: LlmDisplayInfo, locale: string): string {
    const en = locale === 'en';
    if (info.parseError) {
        const msg = en
            ? `Could not parse ${info.configFile ?? 'repo-wiki.yaml'}.`
            : `无法解析配置文件 ${info.configFile ?? 'repo-wiki.yaml'}。`;
        return `<section class="llm-panel llm-panel-error"><p>${escapeHtml(msg)}</p>${cliEnvironmentFootnote(locale)}</section>`;
    }
    if (!info.configFound) {
        const msg = en
            ? 'No repo-wiki.yaml found; CLI defaults apply. Environment variables may override YAML.'
            : '未检测到 repo-wiki.yaml，将使用 CLI 默认模型；环境变量可能覆盖 YAML。';
        return `<section class="llm-panel"><p class="muted">${escapeHtml(msg)}</p>${cliEnvironmentFootnote(locale)}</section>`;
    }

    const lines: string[] = [];
    const fileLabel = en ? 'Config' : '配置';
    lines.push(
        `<div class="llm-row"><span class="llm-key">${fileLabel}</span> <span>${escapeHtml(info.configFile ?? '')}</span></div>`,
    );

    const providerLabel = en ? 'Provider' : '提供商';
    const providerVal = info.provider ?? (en ? '(default anthropic)' : '（默认 anthropic）');
    lines.push(
        `<div class="llm-row"><span class="llm-key">${providerLabel}</span> <span>${escapeHtml(providerVal)}</span></div>`,
    );

    const primaryModel =
        info.modelUpdate ??
        info.flatModel ??
        (en ? '(default claude-sonnet-4-5)' : '（默认 claude-sonnet-4-5）');
    const primaryLabel = en ? 'Model (update)' : '更新模型';
    lines.push(
        `<div class="llm-row"><span class="llm-key">${primaryLabel}</span> <span>${escapeHtml(primaryModel)}</span></div>`,
    );

    if (info.modelInit) {
        const lab = en ? 'Init' : '初始化';
        lines.push(`<div class="llm-row"><span class="llm-key">${lab}</span> <span>${escapeHtml(info.modelInit)}</span></div>`);
    }
    if (info.modelVerify) {
        const lab = en ? 'Verify' : '校验';
        lines.push(`<div class="llm-row"><span class="llm-key">${lab}</span> <span>${escapeHtml(info.modelVerify)}</span></div>`);
    }
    if (info.flatModel && info.modelUpdate) {
        const lab = en ? 'Flat model' : '扁平 model';
        lines.push(`<div class="llm-row"><span class="llm-key">${lab}</span> <span>${escapeHtml(info.flatModel)}</span></div>`);
    }

    const hint = en
        ? 'Environment variables (e.g. LLM_MODEL) may override YAML.'
        : '环境变量（如 LLM_MODEL）可能覆盖 YAML。';
    lines.push(`<p class="muted llm-hint">${escapeHtml(hint)}</p>`);
    lines.push(cliEnvironmentFootnote(locale));

    return `<section class="llm-panel">${lines.join('')}</section>`;
}

function getGenerateCommand(): string {
    const cfg = vscode.workspace.getConfiguration('repoWikiBrowser');
    const cmd = cfg.get<string>('generateCommand');
    if (typeof cmd === 'string') {
        const trimmed = cmd.trim();
        if (trimmed.length > 0) {
            return trimmed;
        }
    }
    return DEFAULT_GENERATE_COMMAND;
}

function runUpdateWiki(): void {
    runTerminalCommand('Repo Wiki Generate', getGenerateCommand());
}

function getWorkspaceRoot(): string | undefined {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function discoverWikiSource(workspaceRoot: string, preferredRunKey?: string): WikiSource | undefined {
    const runs = discoverManifestRuns(workspaceRoot);
    if (runs.length === 0) {
        return undefined;
    }
    const selected = resolveSelectedRun(runs, preferredRunKey);
    return loadWikiSourceFromRun(workspaceRoot, selected, runs);
}

function discoverManifestRuns(workspaceRoot: string): ManifestRunSummary[] {
    const releaseRoot = path.join(workspaceRoot, '.repo-agent-eval', 'repowiki', 'zh');
    const manifestPath = path.join(releaseRoot, 'manifest.json');
    if (!fs.existsSync(manifestPath)) {
        return [];
    }
    try {
        const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as Record<string, unknown>;
        const navTree = manifest.navigation_tree;
        if (!Array.isArray(navTree) || navTree.length === 0) {
            return [];
        }
        const releaseStatus = pickString(manifest.release_status) ?? pickString(manifest.readiness);
        if (releaseStatus !== 'READY') {
            return [];
        }
        const stat = fs.statSync(manifestPath);
        const runId = pickString(manifest.release_id)
            ?? pickString(manifest.source_run_id)
            ?? pickString(manifest.run_id)
            ?? 'release';
        const generatedAt = pickString(manifest.published_at) ?? pickString(manifest.generated_at);
        const label = generatedAt
            ? `Release · ${runId} · ${generatedAt}`
            : `Release · ${runId} · ${new Date(stat.mtimeMs).toLocaleString()}`;
        return [{
            key: 'repowiki/zh',
            label,
            manifestPath,
            manifestDir: releaseRoot,
            mtimeMs: stat.mtimeMs,
            generatedAt,
        }];
    } catch {
        return [];
    }
}

function resolveSelectedRun(runs: ManifestRunSummary[], preferredRunKey?: string): ManifestRunSummary {
    if (preferredRunKey) {
        const found = runs.find((run) => run.key === preferredRunKey);
        if (found) {
            return found;
        }
    }
    return runs[0];
}

function loadWikiSourceFromRun(
    workspaceRoot: string,
    run: ManifestRunSummary,
    availableRuns: ManifestRunSummary[],
): WikiSource | undefined {
    try {
        const manifest = JSON.parse(fs.readFileSync(run.manifestPath, 'utf8')) as Record<string, unknown>;
        const navigationTreeRaw = manifest.navigation_tree;
        if (!Array.isArray(navigationTreeRaw)) {
            return undefined;
        }
        const navigationTree = navigationTreeRaw as NavigationTreeNode[];
        const files = flattenNavigationTree(navigationTree, run.manifestDir);
        if (files.length === 0) {
            return undefined;
        }
        const wikiGitCommit = pickString(manifest.wiki_git_commit) ?? findCommitInObject(manifest);
        const targetGitCommit = pickString(manifest.target_git_commit) ?? pickString(manifest.commit_hash);
        return {
            manifestPath: run.manifestPath,
            manifestDir: run.manifestDir,
            runKey: run.key,
            runLabel: run.label,
            label: path.relative(workspaceRoot, run.manifestDir) || '.repo-agent-eval',
            availableRuns,
            files,
            manifest,
            navigationTree,
            wikiGitCommit,
            targetGitCommit,
        };
    } catch {
        return undefined;
    }
}

function flattenNavigationTree(tree: NavigationTreeNode[], rootDir: string): WikiFile[] {
    const files: WikiFile[] = [];
    const seen = new Set<string>();

    function traverse(node: NavigationTreeNode, ancestry: string[] = []) {
        const label = pickString(node.label);
        if (node.type === 'page' && node.path && label) {
            const absolutePath = node.absolutePath ? path.resolve(node.absolutePath) : path.resolve(rootDir, node.path);
            const canonicalPath = node.path.replace(/\\/g, '/');
            const key = buildPageKey(canonicalPath, absolutePath);
            if (seen.has(key)) {
                return;
            }
            seen.add(key);
            const headingTitle = getMarkdownTitle(absolutePath);
            const displayLabel = shouldUseHeadingLabel(label) && headingTitle ? headingTitle : label;
            files.push({
                id: key,
                label: displayLabel,
                relativePath: canonicalPath,
                absolutePath,
                type: getNodeType(canonicalPath),
            });
        }
        if (Array.isArray(node.children)) {
            const nextAncestry = label ? [...ancestry, label] : ancestry;
            node.children.forEach((child) => traverse(child, nextAncestry));
        }
    }

    tree.forEach((node) => traverse(node));
    return files;
}

function shouldUseHeadingLabel(label: string): boolean {
    const normalized = label.trim().toLowerCase();
    return normalized === 'index' || normalized === 'overview' || normalized === 'architecture' || normalized === 'module map';
}

function getMarkdownTitle(absolutePath: string): string | undefined {
    if (!fs.existsSync(absolutePath)) {
        return undefined;
    }
    try {
        const content = fs.readFileSync(absolutePath, 'utf8');
        const heading = content.match(/^#\s+(.+)$/m);
        return heading?.[1]?.trim();
    } catch {
        return undefined;
    }
}

function getNodeType(relativePath: string): WikiNodeType {
    const normalized = relativePath.toLowerCase();
    if (normalized.includes('00-overview') || normalized.includes('01-architecture')) {
        return 'overview';
    }
    if (normalized.includes('/modules/')) {
        return 'module';
    }
    if (normalized.includes('api')) {
        return 'api';
    }
    if (normalized.includes('data') || normalized.includes('model')) {
        return 'data';
    }
    if (normalized.includes('operations')) {
        return 'operations';
    }
    if (normalized.includes('development')) {
        return 'development';
    }
    if (normalized.includes('security')) {
        return 'security';
    }
    if (normalized.includes('/sections/')) {
        return 'section';
    }
    return 'other';
}

function getGitStatus(workspaceRoot: string, source: WikiSource): GitStatus {
    const currentCommit = runGit(workspaceRoot, ['rev-parse', 'HEAD']);
    const wikiCommit = source.wikiGitCommit;
    const targetCommit = source.targetGitCommit;

    if (!currentCommit) {
        return {
            wikiCommit,
            isStale: false,
            message: '当前工作区未检测到 git commit，无法比较 Wiki 版本。',
        };
    }

    if (!wikiCommit) {
        return {
            currentCommit,
            isStale: false,
            message: `未检测到 Wiki commit 记录。当前代码版本为 ${shortCommit(currentCommit)}，建议更新 Wiki 后建立版本基线。`,
        };
    }

    if (targetCommit && (currentCommit.startsWith(targetCommit) || targetCommit.startsWith(currentCommit))) {
        return {
            currentCommit,
            wikiCommit,
            isStale: false,
            changedFiles: 0,
            message: `Wiki 与当前代码版本一致，commit ${shortCommit(currentCommit)}。`,
        };
    }

    if (!targetCommit && (currentCommit.startsWith(wikiCommit) || wikiCommit.startsWith(currentCommit))) {
        return {
            currentCommit,
            wikiCommit,
            isStale: false,
            changedFiles: 0,
            message: `Wiki 与当前代码版本一致，commit ${shortCommit(currentCommit)}。`,
        };
    }

    const baselineCommit = targetCommit ?? wikiCommit;
    const changedFiles = countChangedFiles(workspaceRoot, baselineCommit, currentCommit);
    return {
        currentCommit,
        wikiCommit,
        changedFiles,
        isStale: true,
        message: `代码已更新。当前 Wiki 基于 commit ${shortCommit(wikiCommit)}，最新版本为 ${shortCommit(currentCommit)}${changedFiles !== undefined ? `（共 ${changedFiles} 个文件变更）` : ''}。是否更新 Wiki?`,
    };
}

function findCommitInObject(value: unknown): string | undefined {
    if (!value || typeof value !== 'object') {
        return undefined;
    }

    for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
        if (typeof raw === 'string' && /(?:commit|git.*hash|revision|sha)/i.test(key) && /^[0-9a-f]{7,40}$/i.test(raw)) {
            return raw;
        }
        if (raw && typeof raw === 'object') {
            const nested = findCommitInObject(raw);
            if (nested) {
                return nested;
            }
        }
    }

    return undefined;
}

function runGit(workspaceRoot: string, args: string[]): string | undefined {
    try {
        return childProcess.execFileSync('git', args, {
            cwd: workspaceRoot,
            encoding: 'utf8',
            stdio: ['ignore', 'pipe', 'ignore'],
        }).trim();
    } catch {
        return undefined;
    }
}

function countChangedFiles(workspaceRoot: string, fromCommit: string, toCommit: string): number | undefined {
    const output = runGit(workspaceRoot, ['diff', '--name-only', `${fromCommit}..${toCommit}`]);
    if (output === undefined) {
        return undefined;
    }
    if (!output.trim()) {
        return 0;
    }
    return output.split(/\r?\n/).filter(Boolean).length;
}

function shortCommit(commit: string): string {
    return commit.slice(0, 12);
}

function openMarkdownPreview(absolutePath: string): void {
    if (!fs.existsSync(absolutePath)) {
        vscode.window.showWarningMessage(`Wiki page not found: ${absolutePath}`);
        return;
    }
    vscode.commands.executeCommand('markdown.showPreview', vscode.Uri.file(absolutePath));
}

function runTerminalCommand(name: string, command: string): void {
    const workspaceRoot = getWorkspaceRoot();
    const terminal = vscode.window.createTerminal({ name, cwd: workspaceRoot });
    terminal.show();
    terminal.sendText(command);
}

function renderNavigationTree(nodes: NavigationTreeNode[], files: WikiFile[]): string {
    const pageLabelMap = new Map<string, string>();
    for (const file of files) {
        pageLabelMap.set(file.id, file.label);
    }
    return nodes.map((node, index) => renderTreeNode(node, index < 3, pageLabelMap)).join('');
}

function renderTreeNode(node: NavigationTreeNode, open: boolean, pageLabelMap: Map<string, string>): string {
    const label = escapeHtml(pickString(node.label) ?? '(unnamed)');
    const children = Array.isArray(node.children) ? node.children : [];
    if ((node.type ?? '').toLowerCase() === 'page' && node.path) {
        const key = buildPageKey(node.path, node.absolutePath);
        const displayLabel = pageLabelMap.get(key) ?? (pickString(node.label) ?? node.path);
        const id = escapeHtml(key);
        const title = escapeHtml(node.path);
        return `<button class="node ${getNodeType(node.path)}" data-id="${id}" title="${title}">${escapeHtml(displayLabel)}</button>`;
    }

    if (children.length === 0) {
        return '';
    }

    const childHtml = children.map((child) => renderTreeNode(child, false, pageLabelMap)).join('');
    return `
        <details ${open ? 'open' : ''}>
            <summary>${label}</summary>
            <div class="children">${childHtml}</div>
        </details>
    `;
}

function buildPageKey(filePath: string, absolutePath?: string): string {
    const canonical = filePath.replace(/\\/g, '/');
    return absolutePath ? `${canonical}::${path.resolve(absolutePath)}` : canonical;
}

function baseHtml(body: string): string {
    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            color-scheme: light dark;
            --border: var(--vscode-sideBarSectionHeader-border, rgba(128, 128, 128, 0.28));
            --muted: var(--vscode-descriptionForeground);
            --button: var(--vscode-button-background);
            --button-fg: var(--vscode-button-foreground);
            --button-secondary: var(--vscode-button-secondaryBackground);
            --button-secondary-fg: var(--vscode-button-secondaryForeground);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 14px 12px 20px;
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-sideBar-foreground);
            background: var(--vscode-sideBar-background);
        }
        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 18px;
        }
        .brand {
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .llm-panel {
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
            margin-bottom: 12px;
            font-size: 12px;
            line-height: 1.4;
        }
        .run-panel {
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
            margin-bottom: 12px;
        }
        .run-panel-title {
            font-size: 11px;
            color: var(--muted);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .run-meta {
            margin: 8px 0 0;
            font-size: 11px;
            word-break: break-all;
        }
        .llm-panel-error {
            color: var(--vscode-errorForeground, #f14c4c);
        }
        .llm-row {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-bottom: 4px;
        }
        .llm-key {
            color: var(--muted);
            flex: 0 0 auto;
            min-width: 4.5em;
        }
        .llm-hint {
            margin: 8px 0 0;
            font-size: 11px;
        }
        select {
            max-width: 132px;
            border: 1px solid var(--vscode-dropdown-border);
            background: var(--vscode-dropdown-background);
            color: var(--vscode-dropdown-foreground);
            padding: 4px 8px;
            border-radius: 3px;
        }
        .notice {
            border-bottom: 1px solid var(--border);
            padding-bottom: 14px;
            margin-bottom: 14px;
        }
        .notice p {
            margin: 0 0 10px;
            line-height: 1.45;
        }
        .notice.stale p {
            color: var(--vscode-editorWarning-foreground, var(--vscode-sideBar-foreground));
        }
        .actions {
            display: grid;
            grid-template-columns: 1fr 1fr 34px;
            gap: 8px;
        }
        button {
            width: 100%;
            border: 0;
            border-radius: 3px;
            padding: 7px 10px;
            color: var(--button-secondary-fg);
            background: var(--button-secondary);
            cursor: pointer;
            font: inherit;
        }
        button.primary {
            color: var(--button-fg);
            background: var(--button);
        }
        button.icon {
            padding-left: 0;
            padding-right: 0;
        }
        .tree details {
            border-bottom: 1px solid rgba(128, 128, 128, 0.14);
            padding: 2px 0;
        }
        .tree summary {
            cursor: pointer;
            padding: 7px 2px;
            font-size: 14px;
            font-weight: 600;
            user-select: none;
        }
        .children {
            padding: 0 0 5px 16px;
        }
        .node {
            display: block;
            width: 100%;
            text-align: left;
            background: transparent;
            color: var(--vscode-sideBar-foreground);
            border-radius: 3px;
            padding: 5px 7px;
            line-height: 1.35;
            white-space: normal;
        }
        .node:hover {
            background: var(--vscode-list-hoverBackground);
        }
        .muted {
            color: var(--muted);
            line-height: 1.45;
        }
        .panel code {
            font-family: var(--vscode-editor-font-family, ui-monospace, SFMono-Regular, Menlo, monospace);
            font-size: 11px;
        }
    </style>
</head>
<body>
${body}
<script>
    const vscode = acquireVsCodeApi();
    document.addEventListener('click', (event) => {
        const target = event.target;
        if (!target || !target.dataset) return;
        if (target.dataset.id) {
            vscode.postMessage({ command: 'openPage', id: target.dataset.id });
        }
        if (target.dataset.command) {
            vscode.postMessage({ command: target.dataset.command });
        }
    });
    const locale = document.getElementById('locale');
    if (locale) {
        locale.addEventListener('change', () => {
            vscode.postMessage({ command: 'locale', locale: locale.value });
        });
    }
    const runSelect = document.getElementById('runSelect');
    if (runSelect) {
        runSelect.addEventListener('change', () => {
            vscode.postMessage({ command: 'selectRun', runKey: runSelect.value });
        });
    }
</script>
</body>
</html>`;
}

function escapeHtml(value: string): string {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
