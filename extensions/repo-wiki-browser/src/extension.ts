import * as childProcess from 'child_process';
import * as fs from 'fs';
import yaml from 'js-yaml';
import * as path from 'path';
import * as vscode from 'vscode';

const DEFAULT_GENERATE_COMMAND = 'uv run repo-wiki generate --profile qoder-like';
const SECRET_LLM_API_KEY = 'repoWikiBrowser.llm.apiKey';
const DEFAULT_LLM_API_KEY_ENV = 'REPO_WIKI_LLM_API_KEY';
const DEFAULT_LLM_SOURCE: LlmSource = 'extension';
const LLM_SOURCES = ['extension', 'yaml', 'environment'] as const;
const RELEASE_RELATIVE_ROOT = path.join('.repo-agent-eval', 'repowiki', 'zh');
const RELEASE_CONTENT_DIR = 'content';
const RELEASE_META_DIR = 'meta';

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
    contentDir: string;
    runKey: string;
    runLabel: string;
    label: string;
    availableRuns: ManifestRunSummary[];
    files: WikiFile[];
    manifest: Record<string, unknown>;
    navigationTree: NavigationTreeNode[];
    wikiGitCommit?: string;
    targetGitCommit?: string;
    releaseMeta?: Record<string, unknown>;
    evidenceIndex?: EvidenceIndex;
    pageRegistry?: PageRegistry;
    workspaceRoot: string;
    relatedPagesBySource: Map<string, RelatedWikiPage[]>;
}

interface RelatedWikiPage {
    relativePath: string;
    label: string;
    fileId: string;
    pageId?: string;
    category?: string;
    pageType?: string;
    evidenceCount: number;
    sourcePath?: string;
    startLine?: number;
    endLine?: number;
    citations: SourceCitation[];
}

interface EvidenceSpan {
    pageRelativePath?: string;
    sourcePath?: string;
    startLine?: number;
    endLine?: number;
}

interface EvidenceIndex {
    spans: EvidenceSpan[];
}

interface PageRegistryEntry {
    pageId?: string;
    relativePath: string;
    category?: string;
    pageType?: string;
}

interface PageRegistry {
    pages: PageRegistryEntry[];
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

type FreshnessState = 'fresh' | 'stale' | 'unknown';

interface GitStatus {
    currentCommit?: string;
    wikiCommit?: string;
    baselineCommit?: string;
    changedFiles?: number;
    changedFilePaths?: string[];
    impactedPages?: RelatedWikiPage[];
    freshness: FreshnessState;
    isStale: boolean;
    message: string;
}

type LlmSource = typeof LLM_SOURCES[number];

interface LlmEffectiveConfig {
    source: LlmSource;
    provider?: string;
    model?: string;
    baseUrl?: string;
    apiKeyEnv: string;
    apiKeyPresent: boolean;
    apiKeyEnvError?: string;
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
    settings: LlmEffectiveConfig;
}

let sidebarProvider: RepoWikiSidebarProvider;

export function activate(context: vscode.ExtensionContext) {
    sidebarProvider = new RepoWikiSidebarProvider(context.extensionUri, context.secrets);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('repoWikiBrowser.sidebar', sidebarProvider),
        vscode.commands.registerCommand('repoWikiBrowser.openViewer', () => sidebarProvider.openDefaultPage()),
        vscode.commands.registerCommand('repoWikiBrowser.refreshTree', () => sidebarProvider.refresh()),
        vscode.commands.registerCommand('repoWikiBrowser.runVerify', () => runTerminalCommand('Repo Wiki Verify', 'repo-wiki verify --ci')),
        vscode.commands.registerCommand('repoWikiBrowser.updateWiki', () => runUpdateWiki(context.secrets)),
        vscode.commands.registerCommand('repoWikiBrowser.syncWiki', () => runTerminalCommand('Repo Wiki Sync', 'repo-wiki sync')),
        vscode.commands.registerCommand('repoWikiBrowser.configureLlm', () => configureLlmSettings(context.secrets)),
        vscode.commands.registerCommand('repoWikiBrowser.setApiKey', () => setLlmApiKey(context.secrets)),
        vscode.commands.registerCommand('repoWikiBrowser.clearApiKey', () => clearLlmApiKey(context.secrets)),
        vscode.commands.registerCommand('repoWikiBrowser.testLlmConfig', () => testLlmConfig(context.secrets)),
        vscode.commands.registerCommand('repoWikiBrowser.openPage', (pageIdOrPath: unknown) => sidebarProvider.openPageCommand(pageIdOrPath)),
        vscode.commands.registerCommand('repoWikiBrowser.openSourceCitation', (citation: unknown) => openSourceCitation(citation)),
        vscode.window.onDidChangeActiveTextEditor(() => sidebarProvider.refresh()),
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

    constructor(
        private readonly extensionUri: vscode.Uri,
        private readonly secrets: vscode.SecretStorage,
    ) {}

    resolveWebviewView(webviewView: vscode.WebviewView): void {
        this.view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.extensionUri],
        };

        webviewView.webview.onDidReceiveMessage((message) => {
            switch (message.command) {
                case 'openPage': {
                    this.openPageCommand(message.id);
                    break;
                }
                case 'openSourceCitation':
                    openSourceCitation(message.citation);
                    break;
                case 'refresh':
                    this.refresh();
                    break;
                case 'update':
                    runUpdateWiki(this.secrets);
                    break;
                case 'sync':
                    runTerminalCommand('Repo Wiki Sync', 'repo-wiki sync');
                    break;
                case 'configureLlm':
                    configureLlmSettings(this.secrets);
                    break;
                case 'setApiKey':
                    setLlmApiKey(this.secrets);
                    break;
                case 'clearApiKey':
                    clearLlmApiKey(this.secrets);
                    break;
                case 'testLlmConfig':
                    testLlmConfig(this.secrets);
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

    async refresh(): Promise<void> {
        const workspaceRoot = getWorkspaceRoot();
        if (!this.view) {
            return;
        }

        if (!workspaceRoot) {
            this.view.webview.html = this.renderNoWorkspace();
            return;
        }

        const llmInfo = await loadLlmDisplayInfo(workspaceRoot, this.secrets);
        this.source = discoverWikiSource(workspaceRoot, this.selectedRunKey);
        this.selectedRunKey = this.source?.runKey;
        this.fileById.clear();
        if (this.source) {
            for (const file of this.source.files) {
                this.fileById.set(file.id, file);
            }
        }

        if (!this.source) {
            this.view.webview.html = this.renderNoWikiRuns(workspaceRoot, llmInfo);
            return;
        }

        const gitStatus = getGitStatus(workspaceRoot, this.source);
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

    openPageCommand(pageIdOrPath: unknown): void {
        const id = String(pageIdOrPath ?? '');
        const file = this.fileById.get(id);
        if (!file) {
            vscode.window.showWarningMessage('Rejected Wiki page request outside the published READY release.');
            return;
        }
        const source = this.source;
        const refreshed = source ? safeResolveReleasePagePath(source.contentDir, file.relativePath, source.workspaceRoot, source.manifestDir, source.manifestPath) : undefined;
        if (!refreshed || refreshed.relativePath !== file.relativePath) {
            vscode.window.showWarningMessage('Rejected Wiki page request outside the published READY release.');
            return;
        }
        openMarkdownPreview(refreshed.absolutePath);
    }

    private renderNoWorkspace(): string {
        return baseHtml(`
            <section class="panel">
                <h1>REPO WIKI</h1>
                <p class="muted">Open a repository workspace to browse wiki content.</p>
            </section>
        `);
    }

    private renderNoWikiRuns(workspaceRoot: string, llmInfo: LlmDisplayInfo): string {
        const releaseManifestPath = path.join(workspaceRoot, '.repo-agent-eval', 'repowiki', 'zh', 'manifest.json');
        return baseHtml(`
            <section class="panel">
                <h1>REPO WIKI</h1>
                <p class="muted">未检测到已发布的 READY Wiki。</p>
                <p class="muted">请先发布：<code>.repo-agent-eval/repowiki/zh/manifest.json</code></p>
                <p class="muted">插件只读取 release manifest 的 <code>navigation_tree</code>，不回退扫描 run 目录或 <code>docs/</code>。</p>
                <p class="muted">查找文件：<code>${escapeHtml(releaseManifestPath)}</code></p>
                ${renderLlmPanel(llmInfo, this.locale)}
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
        const activeSourceRelated = getActiveSourceRelatedPages(source);
        const relatedPanel = renderRelatedWikiPanel(activeSourceRelated, gitStatus.impactedPages ?? []);

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
                ${renderReleaseProvenance(source, gitStatus)}
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
                ${relatedPanel}
                ${treeHtml}
            </nav>
        `);
    }
}

function pickString(value: unknown): string | undefined {
    return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined;
}

/** Match Python `create_viewer_for_workspace_release` READY detection (manifest fields). */
function pickReleaseReadyString(manifest: Record<string, unknown>): string | undefined {
    const direct =
        pickString(manifest.release_status) ??
        pickString(manifest.readiness_state) ??
        pickString(manifest.readiness);
    if (direct) {
        return direct;
    }
    const nested = manifest.readiness;
    if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
        const r = nested as Record<string, unknown>;
        return pickString(r.readiness_state) ?? pickString(r.status);
    }
    return undefined;
}

async function loadLlmDisplayInfo(workspaceRoot: string, secrets: vscode.SecretStorage): Promise<LlmDisplayInfo> {
    const settings = await getLlmEffectiveConfig(secrets);
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
                return { configFound: false, configFile: name, parseError: true, settings };
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
                settings,
            };
        } catch {
            return { configFound: false, configFile: name, parseError: true, settings };
        }
    }
    return { configFound: false, settings };
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
    const lines: string[] = [];
    const title = en ? 'LLM Settings' : 'LLM 设置';
    const sourceLabels: Record<LlmSource, string> = {
        extension: en ? 'Extension settings + SecretStorage' : '扩展设置 + SecretStorage',
        yaml: en ? 'YAML config + optional SecretStorage key' : 'YAML 配置 + 可选 SecretStorage Key',
        environment: en ? 'Shell/process environment' : 'Shell/进程环境',
    };
    lines.push(`<div class="run-panel-title">${escapeHtml(title)}</div>`);
    lines.push(`<p class="muted llm-hint">${escapeHtml(en ? `Source: ${sourceLabels[info.settings.source]}` : `来源：${sourceLabels[info.settings.source]}`)}</p>`);
    lines.push(renderLlmRow(en ? 'Source' : '来源', info.settings.source));
    lines.push(renderLlmRow(en ? 'Provider' : '提供商', info.settings.provider || (en ? '(CLI/YAML default)' : '（CLI/YAML 默认）')));
    lines.push(renderLlmRow(en ? 'Model' : '模型', info.settings.model || (en ? '(CLI/YAML default)' : '（CLI/YAML 默认）')));
    lines.push(renderLlmRow(en ? 'Base URL' : 'Base URL', info.settings.baseUrl ?? (en ? '(not set)' : '（未设置）')));
    lines.push(renderLlmRow(en ? 'API key env' : 'API Key 环境变量', info.settings.apiKeyEnv));
    lines.push(renderLlmRow(en ? 'API key' : 'API Key', info.settings.apiKeyPresent ? (en ? 'stored' : '已保存') : (en ? 'not stored' : '未保存')));

    if (info.settings.apiKeyEnvError) {
        lines.push(`<p class="muted llm-hint llm-warning">${escapeHtml(info.settings.apiKeyEnvError)}</p>`);
    }
    if (info.parseError) {
        const msg = en
            ? `Could not parse ${info.configFile ?? 'repo-wiki.yaml'}.`
            : `无法解析 ${info.configFile ?? 'repo-wiki.yaml'}。`;
        lines.push(`<p class="muted llm-hint llm-warning">${escapeHtml(msg)}</p>`);
    } else if (info.configFound) {
        lines.push(renderLlmRow(en ? 'YAML visible' : 'YAML 显示', info.configFile ?? 'repo-wiki.yaml'));
        const yamlBits = [
            info.provider ? `provider=${info.provider}` : undefined,
            (info.modelUpdate ?? info.flatModel) ? `model=${info.modelUpdate ?? info.flatModel}` : undefined,
        ].filter((bit): bit is string => Boolean(bit));
        if (yamlBits.length > 0) {
            lines.push(`<p class="muted llm-hint">${escapeHtml((en ? 'YAML summary: ' : 'YAML 摘要：') + yamlBits.join(', '))}</p>`);
        }
    } else {
        const msg = en
            ? 'No repo-wiki.yaml found.'
            : '未检测到 repo-wiki.yaml。';
        lines.push(`<p class="muted llm-hint">${escapeHtml(msg)}</p>`);
    }
    const behavior = en
        ? 'Extension source injects only non-empty provider/model/base URL plus key env. YAML source leaves YAML non-secret fields alone and may inject only the stored key. Environment source injects no LLM override variables.'
        : 'extension 来源只注入非空 provider/model/base URL 和 Key 环境变量；yaml 来源不覆盖 YAML 中的非敏感字段，可仅注入已保存 Key；environment 来源不注入任何 LLM 覆盖变量。';
    lines.push(`<p class="muted llm-hint">${escapeHtml(behavior)}</p>`);

    lines.push(`
        <div class="actions llm-actions">
            <button data-command="configureLlm">${escapeHtml(en ? 'Configure' : '配置')}</button>
            <button data-command="setApiKey">${escapeHtml(en ? 'Set Key' : '设置 Key')}</button>
            <button data-command="testLlmConfig">${escapeHtml(en ? 'Test' : '测试')}</button>
        </div>
        <div class="actions llm-actions llm-actions-secondary">
            <button data-command="clearApiKey">${escapeHtml(en ? 'Clear Key' : '清除 Key')}</button>
            <button data-command="refresh">${escapeHtml(en ? 'Refresh' : '刷新')}</button>
            <span></span>
        </div>
    `);
    lines.push(cliEnvironmentFootnote(locale));

    return `<section class="llm-panel${info.parseError ? ' llm-panel-error' : ''}">${lines.join('')}</section>`;
}

function renderLlmRow(label: string, value: string): string {
    return `<div class="llm-row"><span class="llm-key">${escapeHtml(label)}</span> <span>${escapeHtml(value)}</span></div>`;
}

function renderReleaseProvenance(source: WikiSource, gitStatus: GitStatus): string {
    const releaseStatus = pickReleaseReadyString(source.manifest) ?? pickString(source.releaseMeta?.release_status) ?? 'unknown';
    const releaseId = pickString(source.releaseMeta?.release_id) ?? pickString(source.manifest.release_id) ?? 'unknown';
    const sourceRun = pickString(source.releaseMeta?.source_run_id) ?? pickString(source.manifest.source_run_id) ?? pickString(source.manifest.run_id) ?? 'unknown';
    const publishedAt = pickString(source.releaseMeta?.published_at) ?? pickString(source.manifest.published_at) ?? pickString(source.manifest.generated_at) ?? 'unknown';
    const baselineCommit = gitStatus.baselineCommit ?? source.targetGitCommit ?? source.wikiGitCommit;
    const targetCommit = baselineCommit ? shortCommit(baselineCommit) : 'unknown';
    const currentCommit = gitStatus.currentCommit ? shortCommit(gitStatus.currentCommit) : 'unknown';
    const freshness = gitStatus.freshness === 'stale' ? 'STALE' : gitStatus.freshness === 'fresh' ? 'fresh' : 'UNKNOWN';
    return `
        <div class="provenance">
            ${renderLlmRow('READY', releaseStatus)}
            ${renderLlmRow('Release', releaseId)}
            ${renderLlmRow('Source run', sourceRun)}
            ${renderLlmRow('Published', publishedAt)}
            ${renderLlmRow('Commit', `${targetCommit} → ${currentCommit} (${freshness})`)}
        </div>
    `;
}

function renderRelatedWikiPanel(activeRelated: RelatedWikiPage[], impactedPages: RelatedWikiPage[]): string {
    const citationMap = new Map<string, SourceCitation>();
    const activeHtml = renderRelatedPageList(activeRelated, '当前源文件相关 Wiki', citationMap, 'active');
    const impactedHtml = renderRelatedPageList(impactedPages, '变更文件影响 Wiki', citationMap, 'impacted');
    const citationData = Object.fromEntries(citationMap.entries());
    const citationScript = `<script type="application/json" id="repoWikiCitationMap">${safeJsonForInline(citationData)}</script>`;
    if (!activeHtml && !impactedHtml) {
        return `<section class="related"><p class="muted">READY 元数据未提供当前源文件或变更文件的 Wiki 关联。</p>${citationScript}</section>`;
    }
    return `<section class="related">${activeHtml}${impactedHtml}${citationScript}</section>`;
}

function renderRelatedPageList(pages: RelatedWikiPage[], title: string, citationMap: Map<string, SourceCitation>, scope: string): string {
    if (pages.length === 0) {
        return '';
    }
    const items = pages.slice(0, 12).map((page, index) => {
        const meta = [page.category, page.pageType, `${page.evidenceCount} citation${page.evidenceCount === 1 ? '' : 's'}`]
            .filter(Boolean)
            .join(' · ');
        const citationButtons = page.citations.slice(0, 3).map((citation, citationIndex) => {
            const citationId = `${scope}-${index}-${citationIndex}`;
            citationMap.set(citationId, citation);
            return `<button class="citation" data-citation-id="${escapeHtml(citationId)}" title="Open source citation">L${escapeHtml(formatLineRange(citation.startLine, citation.endLine))}</button>`;
        }).join('');
        return `<li><button class="related-page" data-id="${escapeHtml(page.fileId)}" title="${escapeHtml(page.relativePath)}"><span>${escapeHtml(page.label)}</span><small>${escapeHtml(meta || page.relativePath)}</small></button>${citationButtons}</li>`;
    }).join('');
    return `<div class="related-group"><div class="run-panel-title">${escapeHtml(title)}</div><ul>${items}</ul></div>`;
}

function formatLineRange(startLine?: number, endLine?: number): string {
    if (!startLine) {
        return '?';
    }
    return endLine && endLine !== startLine ? `${startLine}-${endLine}` : String(startLine);
}

function safeJsonForInline(value: unknown): string {
    return JSON.stringify(value)
        .replace(/</g, '\\u003c')
        .replace(/>/g, '\\u003e')
        .replace(/&/g, '\\u0026')
        .replace(/\u2028/g, '\\u2028')
        .replace(/\u2029/g, '\\u2029');
}

function getActiveSourceRelatedPages(source: WikiSource): RelatedWikiPage[] {
    const workspaceRoot = getWorkspaceRoot();
    const activePath = vscode.window.activeTextEditor?.document.uri.fsPath;
    if (!workspaceRoot || !activePath) {
        return [];
    }
    const relativePath = normalizeWorkspaceRelativePath(path.relative(workspaceRoot, activePath));
    return relativePath ? (source.relatedPagesBySource.get(relativePath) ?? []) : [];
}

function isValidEnvName(value: string): boolean {
    return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value);
}

function normalizeSource(value: string | undefined): LlmSource {
    const trimmed = (value ?? '').trim();
    return (LLM_SOURCES as readonly string[]).includes(trimmed) ? trimmed as LlmSource : DEFAULT_LLM_SOURCE;
}

function normalizeEnvName(value: string | undefined): { apiKeyEnv: string; apiKeyEnvError?: string } {
    const trimmed = (value ?? '').trim();
    if (!trimmed) {
        return { apiKeyEnv: DEFAULT_LLM_API_KEY_ENV };
    }
    if (isValidEnvName(trimmed)) {
        return { apiKeyEnv: trimmed };
    }
    return {
        apiKeyEnv: trimmed,
        apiKeyEnvError: `Invalid repoWikiBrowser.llm.apiKeyEnv "${trimmed}". Use a valid environment variable name or clear the setting to use ${DEFAULT_LLM_API_KEY_ENV}.`,
    };
}

function getConfiguredLlmValues(): Omit<LlmEffectiveConfig, 'apiKeyPresent'> {
    const cfg = vscode.workspace.getConfiguration('repoWikiBrowser.llm');
    const provider = (cfg.get<string>('provider') ?? '').trim() || undefined;
    const model = (cfg.get<string>('model') ?? '').trim() || undefined;
    const baseUrlRaw = (cfg.get<string>('baseUrl') ?? '').trim();
    const { apiKeyEnv, apiKeyEnvError } = normalizeEnvName(cfg.get<string>('apiKeyEnv'));
    return {
        source: normalizeSource(cfg.get<string>('source')),
        provider,
        model,
        baseUrl: baseUrlRaw || undefined,
        apiKeyEnv,
        apiKeyEnvError,
    };
}

async function getLlmEffectiveConfig(secrets: vscode.SecretStorage): Promise<LlmEffectiveConfig> {
    const values = getConfiguredLlmValues();
    const storedKey = await secrets.get(SECRET_LLM_API_KEY);
    return { ...values, apiKeyPresent: Boolean(storedKey) };
}

async function buildLlmTerminalEnv(secrets: vscode.SecretStorage): Promise<Record<string, string>> {
    ensureWorkspaceTrusted();
    const cfg = getConfiguredLlmValues();
    ensureValidApiKeyEnv(cfg);
    const env: Record<string, string> = {};
    if (cfg.source === 'environment') {
        return env;
    }
    if (cfg.source === 'extension') {
        if (cfg.provider) {
            env.LLM_PROVIDER = cfg.provider;
        }
        if (cfg.model) {
            env.LLM_MODEL = cfg.model;
        }
        if (cfg.baseUrl) {
            env.LLM_BASE_URL = cfg.baseUrl;
        }
        env.LLM_API_KEY_ENV = cfg.apiKeyEnv;
    }
    const apiKey = await secrets.get(SECRET_LLM_API_KEY);
    if (apiKey) {
        const confirmed = await confirmSecretInjection(cfg);
        if (!confirmed) {
            throw new Error('Repo Wiki command cancelled before API key injection.');
        }
        env[cfg.apiKeyEnv] = apiKey;
    }
    return env;
}

function ensureWorkspaceTrusted(): void {
    if (!vscode.workspace.isTrusted) {
        throw new Error('Trust this workspace before running Repo Wiki commands or using a stored API key.');
    }
}

async function confirmSecretInjection(
    cfg: Pick<LlmEffectiveConfig, 'provider' | 'baseUrl' | 'apiKeyEnv'>,
): Promise<boolean> {
    const destination = cfg.baseUrl ?? cfg.provider ?? 'the configured provider endpoint';
    const selected = await vscode.window.showWarningMessage(
        `Run Repo Wiki and expose the stored API key as ${cfg.apiKeyEnv} to this workspace process? Destination: ${destination}.`,
        { modal: true },
        'Run with API Key',
    );
    return selected === 'Run with API Key';
}

function ensureValidApiKeyEnv(cfg: Pick<LlmEffectiveConfig, 'apiKeyEnvError'>): void {
    if (cfg.apiKeyEnvError) {
        throw new Error(cfg.apiKeyEnvError);
    }
}

async function configureLlmSettings(secrets: vscode.SecretStorage): Promise<void> {
    const cfg = getConfiguredLlmValues();
    try {
        ensureValidApiKeyEnv(cfg);
    } catch (error) {
        vscode.window.showErrorMessage(error instanceof Error ? error.message : String(error));
        return;
    }
    const source = await vscode.window.showQuickPick(
        [
            { label: 'extension', description: 'Inject non-empty extension settings into generated CLI runs.' },
            { label: 'yaml', description: 'Let repo-wiki.yaml provide non-secret LLM fields; optionally inject stored key.' },
            { label: 'environment', description: 'Inject no LLM overrides; use shell/process environment.' },
        ],
        { title: 'Repo Wiki LLM Source', placeHolder: 'Choose where repo-wiki should read LLM configuration' },
    );
    if (source === undefined) {
        return;
    }
    const providerPick = await vscode.window.showQuickPick(
        [cfg.provider, 'openai', 'anthropic', 'azure_openai', 'gemini', 'ollama', '(clear)'].filter((value, index, arr): value is string => Boolean(value) && arr.indexOf(value) === index),
        { title: 'Repo Wiki LLM Provider', placeHolder: 'Select or type a provider; use (clear) for CLI/YAML default' },
    );
    if (providerPick === undefined) {
        return;
    }
    const provider = await vscode.window.showInputBox({
        title: 'Repo Wiki LLM Provider',
        prompt: 'Provider passed as LLM_PROVIDER only when source=extension and non-empty. Leave blank to use CLI/YAML defaults.',
        value: providerPick === '(clear)' ? '' : providerPick,
        ignoreFocusOut: true,
    });
    if (provider === undefined) {
        return;
    }
    const model = await vscode.window.showInputBox({
        title: 'Repo Wiki LLM Model',
        prompt: 'Model passed as LLM_MODEL only when source=extension and non-empty. Leave blank to use CLI/YAML defaults.',
        value: cfg.model ?? '',
        ignoreFocusOut: true,
    });
    if (model === undefined) {
        return;
    }
    const baseUrl = await vscode.window.showInputBox({
        title: 'Repo Wiki LLM Base URL',
        prompt: 'Optional. Injected as LLM_BASE_URL only when source=extension and non-empty. Leave blank to clear.',
        value: cfg.baseUrl ?? '',
        ignoreFocusOut: true,
    });
    if (baseUrl === undefined) {
        return;
    }
    const apiKeyEnv = await vscode.window.showInputBox({
        title: 'Repo Wiki API Key Environment Variable',
        prompt: `Environment variable name for the stored API key. Leave blank to use ${DEFAULT_LLM_API_KEY_ENV}.`,
        value: cfg.apiKeyEnv,
        validateInput: (value) => {
            const trimmed = value.trim();
            return !trimmed || isValidEnvName(trimmed) ? undefined : 'Use a valid environment variable name.';
        },
        ignoreFocusOut: true,
    });
    if (apiKeyEnv === undefined) {
        return;
    }

    const settings = vscode.workspace.getConfiguration('repoWikiBrowser.llm');
    await settings.update('source', source.label, vscode.ConfigurationTarget.Workspace);
    await settings.update('provider', provider.trim(), vscode.ConfigurationTarget.Workspace);
    await settings.update('model', model.trim(), vscode.ConfigurationTarget.Workspace);
    await settings.update('baseUrl', baseUrl.trim(), vscode.ConfigurationTarget.Workspace);
    await settings.update('apiKeyEnv', apiKeyEnv.trim() || DEFAULT_LLM_API_KEY_ENV, vscode.ConfigurationTarget.Workspace);
    sidebarProvider?.refresh();

    const setKey = await vscode.window.showInformationMessage('Repo Wiki LLM settings saved. Empty provider/model/base URL values will not override CLI/YAML defaults.', 'Set API Key', 'Test Config');
    if (setKey === 'Set API Key') {
        await setLlmApiKey(secrets);
    } else if (setKey === 'Test Config') {
        await testLlmConfig(secrets);
    }
}

async function setLlmApiKey(secrets: vscode.SecretStorage): Promise<void> {
    const key = await vscode.window.showInputBox({
        title: 'Repo Wiki API Key',
        prompt: 'Stored in VS Code SecretStorage and injected only into CLI process environment.',
        password: true,
        ignoreFocusOut: true,
        validateInput: (value) => value.trim() ? undefined : 'API key cannot be empty.',
    });
    if (key === undefined) {
        return;
    }
    await secrets.store(SECRET_LLM_API_KEY, key.trim());
    sidebarProvider?.refresh();
    vscode.window.showInformationMessage('Repo Wiki API key stored in SecretStorage.');
}

async function clearLlmApiKey(secrets: vscode.SecretStorage): Promise<void> {
    await secrets.delete(SECRET_LLM_API_KEY);
    sidebarProvider?.refresh();
    vscode.window.showInformationMessage('Repo Wiki API key cleared from SecretStorage.');
}

async function testLlmConfig(secrets: vscode.SecretStorage): Promise<void> {
    const workspaceRoot = getWorkspaceRoot();
    const cfg = await getLlmEffectiveConfig(secrets);
    try {
        ensureValidApiKeyEnv(cfg);
    } catch (error) {
        vscode.window.showErrorMessage(error instanceof Error ? error.message : String(error));
        return;
    }
    const secretValue = await secrets.get(SECRET_LLM_API_KEY);
    let env: NodeJS.ProcessEnv;
    try {
        env = { ...process.env, ...(await buildLlmTerminalEnv(secrets)) } as NodeJS.ProcessEnv;
    } catch (error) {
        vscode.window.showErrorMessage(error instanceof Error ? error.message : String(error));
        return;
    }
    childProcess.execFile('repo-wiki', ['config', '--ci'], { cwd: workspaceRoot, env, shell: false, encoding: 'utf8' }, (error, stdout, stderr) => {
        const combined = redactDiagnostics(`${stdout ?? ''}${stderr ? `\n${stderr}` : ''}`, secretValue, cfg.apiKeyEnv);
        const ok = !error;
        const summary = `${ok ? 'OK' : 'FAIL'} repo-wiki config --ci · source=${cfg.source} · provider=${cfg.provider ?? '(CLI/YAML default)'} · model=${cfg.model ?? '(CLI/YAML default)'} · baseUrl=${cfg.baseUrl ?? '(not set)'} · apiKeyPresent=${cfg.apiKeyPresent ? 'yes' : 'no'}`;
        const channel = vscode.window.createOutputChannel('Repo Wiki Config');
        channel.clear();
        channel.appendLine(summary);
        if (combined.trim()) {
            channel.appendLine('');
            channel.appendLine(combined.trim());
        }
        const action = 'Show Diagnostics';
        const message = ok ? `Repo Wiki config OK. ${summary}` : `Repo Wiki config FAIL. ${summary}`;
        vscode.window.showInformationMessage(message, action).then((selected) => {
            if (selected === action) {
                channel.show(true);
            }
        });
    });
}

function redactDiagnostics(text: string, secretValue?: string, apiKeyEnv?: string): string {
    let redacted = text;
    if (secretValue) {
        redacted = redacted.split(secretValue).join('[REDACTED_API_KEY]');
    }
    if (apiKeyEnv) {
        redacted = redacted.replace(new RegExp(`(${escapeRegExp(apiKeyEnv)}\\s*[=:]\\s*)\\S+`, 'gi'), '$1[REDACTED]');
    }
    redacted = redacted.replace(/(api[_-]?key\s*[=:]\s*)\S+/gi, '$1[REDACTED]');
    redacted = redacted.replace(/(authorization\s*:\s*bearer\s+)\S+/gi, '$1[REDACTED]');
    return redacted;
}

function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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

async function runUpdateWiki(secrets: vscode.SecretStorage): Promise<void> {
    try {
        const env = await buildLlmTerminalEnv(secrets);
        runTerminalCommand('Repo Wiki Generate', getGenerateCommand(), env);
    } catch (error) {
        vscode.window.showErrorMessage(error instanceof Error ? error.message : String(error));
    }
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
    const releaseRootCandidate = path.join(workspaceRoot, RELEASE_RELATIVE_ROOT);
    const releaseRoot = resolveExistingDirectoryInside(workspaceRoot, releaseRootCandidate);
    if (!releaseRoot) {
        return [];
    }
    const manifestPath = resolveExistingFileInside(workspaceRoot, releaseRoot, path.join(releaseRoot, 'manifest.json'));
    if (!manifestPath) {
        return [];
    }
    try {
        const manifest = readReleaseSidecarObject(workspaceRoot, releaseRoot, manifestPath);
        if (!manifest) {
            return [];
        }
        const navTree = manifest.navigation_tree;
        if (!Array.isArray(navTree) || navTree.length === 0) {
            return [];
        }
        const releaseStatus = pickReleaseReadyString(manifest);
        if ((releaseStatus ?? '').toUpperCase() !== 'READY') {
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
        const manifest = readReleaseSidecarObject(workspaceRoot, run.manifestDir, run.manifestPath);
        if (!manifest) {
            return undefined;
        }
        const navigationTreeRaw = manifest.navigation_tree;
        if (!Array.isArray(navigationTreeRaw)) {
            return undefined;
        }
        const navigationTree = navigationTreeRaw as NavigationTreeNode[];
        const contentDirCandidate = path.join(run.manifestDir, RELEASE_CONTENT_DIR);
        const contentDir = resolveExistingDirectoryInside(workspaceRoot, contentDirCandidate, run.manifestDir);
        if (!contentDir) {
            return undefined;
        }
        const files = flattenNavigationTree(navigationTree, contentDir, workspaceRoot, run.manifestDir, run.manifestPath);
        if (files.length === 0) {
            return undefined;
        }
        const metaDir = path.join(run.manifestDir, RELEASE_META_DIR);
        const releaseMeta = readReleaseSidecarObject(workspaceRoot, run.manifestDir, path.join(metaDir, 'release.json'));
        const evidenceIndex = loadEvidenceIndex(workspaceRoot, run.manifestDir, path.join(metaDir, 'evidence-index.json'));
        const pageRegistry = loadPageRegistry(workspaceRoot, run.manifestDir, path.join(metaDir, 'page-registry.json'));
        const relatedPagesBySource = buildRelatedPagesBySource(files, evidenceIndex, pageRegistry);
        const wikiGitCommit = pickString(manifest.wiki_git_commit) ?? findCommitInObject(manifest);
        const targetGitCommit = pickString(manifest.target_git_commit)
            ?? pickString(releaseMeta?.target_git_commit)
            ?? pickString(manifest.commit_hash);
        return {
            manifestPath: run.manifestPath,
            manifestDir: run.manifestDir,
            workspaceRoot,
            contentDir,
            runKey: run.key,
            runLabel: run.label,
            label: path.relative(workspaceRoot, run.manifestDir) || '.repo-agent-eval',
            availableRuns,
            files,
            manifest,
            navigationTree,
            wikiGitCommit,
            targetGitCommit,
            releaseMeta,
            evidenceIndex,
            pageRegistry,
            relatedPagesBySource,
        };
    } catch {
        return undefined;
    }
}

function flattenNavigationTree(tree: NavigationTreeNode[], contentDir: string, workspaceRoot: string, releaseRoot: string, manifestPath: string): WikiFile[] {
    const files: WikiFile[] = [];
    const seen = new Set<string>();

    function traverse(node: NavigationTreeNode, ancestry: string[] = []) {
        const label = pickString(node.label);
        if (node.type === 'page' && node.path && label) {
            const resolved = safeResolveReleasePagePath(contentDir, node.path, workspaceRoot, releaseRoot, manifestPath);
            if (!resolved) {
                return;
            }
            const absolutePath = resolved.absolutePath;
            const canonicalPath = resolved.relativePath;
            const key = buildPageKey(canonicalPath);
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

export function safeResolveReleasePagePath(
    contentDir: string,
    candidatePath: string,
    workspaceRoot?: string,
    releaseRoot?: string,
    manifestPath?: string,
): { absolutePath: string; relativePath: string } | undefined {
    const normalizedInput = candidatePath.replace(/\\/g, '/').trim();
    if (
        !normalizedInput ||
        path.isAbsolute(normalizedInput) ||
        /^[a-z][a-z0-9+.-]*:/i.test(normalizedInput) ||
        normalizedInput.split('/').includes('..')
    ) {
        return undefined;
    }

    const contentRoot = path.resolve(contentDir);
    const relativePath = normalizeReleasePageRelativePath(normalizedInput);
    if (!relativePath || path.extname(relativePath).toLowerCase() !== '.md') {
        return undefined;
    }
    const absolutePath = path.resolve(contentRoot, relativePath);
    if (!isPathInside(absolutePath, contentRoot) || !fs.existsSync(absolutePath)) {
        return undefined;
    }
    try {
        const stat = fs.statSync(absolutePath);
        if (!stat.isFile()) {
            return undefined;
        }
        const realContentRoot = fs.realpathSync(contentRoot);
        const realPagePath = fs.realpathSync(absolutePath);
        if (!isPathInside(realPagePath, realContentRoot)) {
            return undefined;
        }
        if (workspaceRoot) {
            const realWorkspace = fs.realpathSync(workspaceRoot);
            if (!isPathInside(realContentRoot, realWorkspace) || !isPathInside(realPagePath, realWorkspace)) {
                return undefined;
            }
            if (releaseRoot) {
                const realReleaseRoot = fs.realpathSync(releaseRoot);
                if (!isPathInside(realReleaseRoot, realWorkspace) || !isPathInside(realContentRoot, realReleaseRoot) || !isPathInside(realPagePath, realReleaseRoot)) {
                    return undefined;
                }
                if (manifestPath) {
                    const realManifest = fs.realpathSync(manifestPath);
                    if (!isPathInside(realManifest, realWorkspace) || !isPathInside(realManifest, realReleaseRoot)) {
                        return undefined;
                    }
                }
            }
        }
        return { absolutePath: realPagePath, relativePath };
    } catch {
        return undefined;
    }
}

function normalizeReleasePageRelativePath(candidatePath: string): string | undefined {
    const normalized = candidatePath.replace(/\\/g, '/').replace(/^\/+/, '');
    const contentPrefix = `${RELEASE_CONTENT_DIR}/`;
    const withoutReleaseRoot = normalized.startsWith(`${RELEASE_RELATIVE_ROOT.replace(/\\/g, '/')}/`)
        ? normalized.slice(`${RELEASE_RELATIVE_ROOT.replace(/\\/g, '/')}/`.length)
        : normalized;
    return withoutReleaseRoot.startsWith(contentPrefix)
        ? withoutReleaseRoot.slice(contentPrefix.length)
        : withoutReleaseRoot;
}

function isPathInside(candidatePath: string, rootPath: string): boolean {
    const relative = path.relative(path.resolve(rootPath), path.resolve(candidatePath));
    return relative === '' || (!!relative && !relative.startsWith('..') && !path.isAbsolute(relative));
}


function resolveExistingDirectoryInside(workspaceRoot: string, candidatePath: string, releaseRoot?: string): string | undefined {
    try {
        if (!fs.existsSync(candidatePath)) {
            return undefined;
        }
        const stat = fs.statSync(candidatePath);
        if (!stat.isDirectory()) {
            return undefined;
        }
        const realWorkspace = fs.realpathSync(workspaceRoot);
        const realDir = fs.realpathSync(candidatePath);
        if (!isPathInside(realDir, realWorkspace)) {
            return undefined;
        }
        if (releaseRoot) {
            const realReleaseRoot = fs.realpathSync(releaseRoot);
            if (!isPathInside(realDir, realReleaseRoot)) {
                return undefined;
            }
        }
        return realDir;
    } catch {
        return undefined;
    }
}

function resolveExistingFileInside(workspaceRoot: string, releaseRoot: string, candidatePath: string): string | undefined {
    try {
        if (!fs.existsSync(candidatePath)) {
            return undefined;
        }
        const stat = fs.statSync(candidatePath);
        if (!stat.isFile()) {
            return undefined;
        }
        const realWorkspace = fs.realpathSync(workspaceRoot);
        const realReleaseRoot = fs.realpathSync(releaseRoot);
        const realFile = fs.realpathSync(candidatePath);
        if (!isPathInside(realFile, realWorkspace) || !isPathInside(realFile, realReleaseRoot)) {
            return undefined;
        }
        return realFile;
    } catch {
        return undefined;
    }
}

function readReleaseSidecarObject(workspaceRoot: string, releaseRoot: string, filePath: string): Record<string, unknown> | undefined {
    const safePath = resolveExistingFileInside(workspaceRoot, releaseRoot, filePath);
    return safePath ? readJsonObject(safePath) : undefined;
}

function readJsonObject(filePath: string): Record<string, unknown> | undefined {
    try {
        const raw = fs.readFileSync(filePath, 'utf8');
        const parsed = JSON.parse(raw) as unknown;
        return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
            ? parsed as Record<string, unknown>
            : undefined;
    } catch {
        return undefined;
    }
}

function loadEvidenceIndex(workspaceRoot: string, releaseRoot: string, filePath: string): EvidenceIndex | undefined {
    const root = readReleaseSidecarObject(workspaceRoot, releaseRoot, filePath);
    const spansRaw = root?.spans;
    if (!Array.isArray(spansRaw)) {
        return undefined;
    }
    const spans = spansRaw
        .map((span): EvidenceSpan | undefined => {
            if (!span || typeof span !== 'object' || Array.isArray(span)) {
                return undefined;
            }
            const item = span as Record<string, unknown>;
            const pageRelativePath = pickString(item.page_relative_path) ?? pickString(item.pageRelativePath) ?? pickString(item.page);
            const sourcePath = pickString(item.source_path) ?? pickString(item.sourcePath) ?? pickString(item.path);
            if (!pageRelativePath || !sourcePath) {
                return undefined;
            }
            return {
                pageRelativePath: normalizeSlashPath(pageRelativePath),
                sourcePath: normalizeSlashPath(sourcePath),
                startLine: pickLineNumber(item.start_line) ?? pickLineNumber(item.startLine) ?? pickLineNumber(item.line),
                endLine: pickLineNumber(item.end_line) ?? pickLineNumber(item.endLine),
            };
        })
        .filter((span): span is EvidenceSpan => Boolean(span));
    return { spans };
}

function loadPageRegistry(workspaceRoot: string, releaseRoot: string, filePath: string): PageRegistry | undefined {
    const root = readReleaseSidecarObject(workspaceRoot, releaseRoot, filePath);
    const pagesRaw = root?.pages;
    if (!Array.isArray(pagesRaw)) {
        return undefined;
    }
    const pages = pagesRaw
        .map((page): PageRegistryEntry | undefined => {
            if (!page || typeof page !== 'object' || Array.isArray(page)) {
                return undefined;
            }
            const item = page as Record<string, unknown>;
            const relativePath = pickString(item.relative_path) ?? pickString(item.relativePath) ?? pickString(item.path);
            if (!relativePath) {
                return undefined;
            }
            return {
                pageId: pickString(item.page_id) ?? pickString(item.pageId) ?? pickString(item.id),
                relativePath: normalizeSlashPath(relativePath),
                category: pickString(item.category),
                pageType: pickString(item.page_type) ?? pickString(item.pageType),
            };
        })
        .filter((page): page is PageRegistryEntry => Boolean(page));
    return { pages };
}

function buildRelatedPagesBySource(files: WikiFile[], evidenceIndex?: EvidenceIndex, pageRegistry?: PageRegistry): Map<string, RelatedWikiPage[]> {
    const pageByPath = new Map(files.map((file) => [normalizeSlashPath(file.relativePath), file]));
    const registryByPath = new Map((pageRegistry?.pages ?? []).map((page) => [normalizeSlashPath(page.relativePath), page]));
    const relatedBySource = new Map<string, Map<string, RelatedWikiPage>>();
    for (const span of evidenceIndex?.spans ?? []) {
        const pagePath = span.pageRelativePath ? normalizeSlashPath(span.pageRelativePath) : undefined;
        const sourcePath = span.sourcePath ? normalizeWorkspaceRelativePath(span.sourcePath) : undefined;
        const file = pagePath ? pageByPath.get(pagePath) : undefined;
        if (!pagePath || !sourcePath || !file) {
            continue;
        }
        const sourcePages = relatedBySource.get(sourcePath) ?? new Map<string, RelatedWikiPage>();
        const existing = sourcePages.get(pagePath);
        const citation: SourceCitation = {
            sourcePath,
            startLine: span.startLine,
            endLine: span.endLine,
        };
        if (existing) {
            existing.evidenceCount += 1;
            existing.startLine = existing.startLine ?? span.startLine;
            existing.endLine = existing.endLine ?? span.endLine;
            if (existing.citations.length < 3) {
                existing.citations.push(citation);
            }
        } else {
            const registry = registryByPath.get(pagePath);
            sourcePages.set(pagePath, {
                relativePath: file.relativePath,
                label: file.label,
                fileId: file.id,
                pageId: registry?.pageId,
                category: registry?.category,
                pageType: registry?.pageType,
                evidenceCount: 1,
                sourcePath,
                startLine: span.startLine,
                endLine: span.endLine,
                citations: [citation],
            });
        }
        relatedBySource.set(sourcePath, sourcePages);
    }

    const result = new Map<string, RelatedWikiPage[]>();
    for (const [sourcePath, pageMap] of relatedBySource) {
        const related = [...pageMap.values()]
            .sort((a, b) => b.evidenceCount - a.evidenceCount || a.relativePath.localeCompare(b.relativePath));
        if (related.length > 0) {
            result.set(sourcePath, related);
        }
    }
    return result;
}

function normalizeSlashPath(value: string): string {
    return value.replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/+/g, '/');
}

function normalizeWorkspaceRelativePath(value: string): string | undefined {
    const normalized = normalizeSlashPath(value.trim());
    if (!normalized || path.isAbsolute(normalized) || /^[a-z][a-z0-9+.-]*:/i.test(normalized) || normalized.split('/').includes('..')) {
        return undefined;
    }
    return normalized;
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
    const baselineCommit = source.targetGitCommit ?? wikiCommit;

    if (!currentCommit) {
        return {
            wikiCommit,
            baselineCommit,
            freshness: 'unknown',
            isStale: false,
            message: '当前工作区未检测到 git commit，无法比较 Wiki 版本。',
        };
    }

    if (!baselineCommit) {
        return {
            currentCommit,
            wikiCommit,
            freshness: 'unknown',
            isStale: false,
            message: `未检测到 Wiki commit 记录。当前代码版本为 ${shortCommit(currentCommit)}，建议更新 Wiki 后建立版本基线。`,
        };
    }

    if (currentCommit.startsWith(baselineCommit) || baselineCommit.startsWith(currentCommit)) {
        return {
            currentCommit,
            wikiCommit,
            baselineCommit,
            freshness: 'fresh',
            isStale: false,
            changedFiles: 0,
            message: `Wiki 与当前代码版本一致，commit ${shortCommit(currentCommit)}。`,
        };
    }

    const changedFilePaths = listChangedFiles(workspaceRoot, baselineCommit, currentCommit);
    const impactedPages = changedFilePaths ? collectRelatedPagesForSources(source, changedFilePaths) : undefined;
    return {
        currentCommit,
        wikiCommit,
        baselineCommit,
        changedFiles: changedFilePaths?.length,
        changedFilePaths,
        impactedPages,
        freshness: 'stale',
        isStale: true,
        message: `代码已更新。当前 Wiki 基于 commit ${shortCommit(baselineCommit)}，最新版本为 ${shortCommit(currentCommit)}${changedFilePaths !== undefined ? `（共 ${changedFilePaths.length} 个文件变更）` : ''}。是否更新 Wiki?`,
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
    return listChangedFiles(workspaceRoot, fromCommit, toCommit)?.length;
}

function listChangedFiles(workspaceRoot: string, fromCommit: string, toCommit: string): string[] | undefined {
    const output = runGit(workspaceRoot, ['diff', '--name-only', `${fromCommit}..${toCommit}`]);
    if (output === undefined) {
        return undefined;
    }
    if (!output.trim()) {
        return [];
    }
    return output.split(/\r?\n/).map((line) => normalizeWorkspaceRelativePath(line)).filter((line): line is string => Boolean(line));
}

function collectRelatedPagesForSources(source: WikiSource, sourcePaths: string[]): RelatedWikiPage[] {
    const byPage = new Map<string, RelatedWikiPage>();
    for (const sourcePath of sourcePaths) {
        for (const page of source.relatedPagesBySource.get(sourcePath) ?? []) {
            const existing = byPage.get(page.relativePath);
            if (existing) {
                existing.evidenceCount += page.evidenceCount;
            } else {
                byPage.set(page.relativePath, { ...page });
            }
        }
    }
    return [...byPage.values()].sort((a, b) => b.evidenceCount - a.evidenceCount || a.relativePath.localeCompare(b.relativePath));
}

function shortCommit(commit: string): string {
    return commit.slice(0, 12);
}

interface SourceCitation {
    sourcePath: string;
    startLine?: number;
    endLine?: number;
}

async function openSourceCitation(citation: unknown): Promise<void> {
    const workspaceRoot = getWorkspaceRoot();
    if (!workspaceRoot) {
        vscode.window.showWarningMessage('No workspace folder open');
        return;
    }
    const parsed = parseSourceCitation(citation);
    if (!parsed) {
        vscode.window.showWarningMessage('Invalid source citation.');
        return;
    }
    const resolved = resolveWorkspaceSourcePath(workspaceRoot, parsed.sourcePath);
    if (!resolved) {
        vscode.window.showWarningMessage('Rejected source citation outside the workspace.');
        return;
    }
    try {
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(resolved));
        const lineCount = Math.max(document.lineCount, 1);
        const startLine = clampLine(parsed.startLine ?? 1, lineCount);
        const endLine = clampLine(parsed.endLine ?? startLine, lineCount);
        const anchor = Math.min(startLine, endLine) - 1;
        const active = Math.max(startLine, endLine) - 1;
        const startCharacter = 0;
        const endCharacter = document.lineAt(active).range.end.character;
        const selection = new vscode.Selection(anchor, startCharacter, active, endCharacter);
        const editor = await vscode.window.showTextDocument(document, { preview: true, selection });
        editor.selection = selection;
        editor.revealRange(selection, vscode.TextEditorRevealType.InCenterIfOutsideViewport);
    } catch (error) {
        vscode.window.showWarningMessage(`Could not open source citation: ${error instanceof Error ? error.message : String(error)}`);
    }
}

export function parseSourceCitation(citation: unknown): SourceCitation | undefined {
    if (typeof citation === 'string') {
        return parseLegacySourceCitation(citation);
    }
    if (!citation || typeof citation !== 'object' || Array.isArray(citation)) {
        return undefined;
    }
    const obj = citation as Record<string, unknown>;
    const sourcePath =
        pickString(obj.source_path) ??
        pickString(obj.sourcePath) ??
        pickString(obj.path) ??
        pickString(obj.file) ??
        pickString(obj.relative_path);
    const normalized = sourcePath ? normalizeWorkspaceRelativePath(sourcePath) : undefined;
    if (!normalized) {
        return undefined;
    }
    return {
        sourcePath: normalized,
        startLine: pickLineNumber(obj.start_line) ?? pickLineNumber(obj.startLine) ?? pickLineNumber(obj.line),
        endLine: pickLineNumber(obj.end_line) ?? pickLineNumber(obj.endLine),
    };
}

function parseLegacySourceCitation(value: string): SourceCitation | undefined {
    const trimmed = value.trim();
    const match = trimmed.match(/^(.+?)(?::(\d+)(?:-(\d+))?)?$/);
    if (!match) {
        return undefined;
    }
    const sourcePath = normalizeWorkspaceRelativePath(match[1]);
    if (!sourcePath) {
        return undefined;
    }
    return {
        sourcePath,
        startLine: match[2] ? Number(match[2]) : undefined,
        endLine: match[3] ? Number(match[3]) : undefined,
    };
}

function pickLineNumber(value: unknown): number | undefined {
    const numeric = typeof value === 'number' ? value : (typeof value === 'string' ? Number(value) : NaN);
    return Number.isFinite(numeric) ? Math.trunc(numeric) : undefined;
}

function clampLine(line: number, lineCount: number): number {
    return Math.min(Math.max(Math.trunc(line), 1), lineCount);
}

function resolveWorkspaceSourcePath(workspaceRoot: string, sourcePath: string): string | undefined {
    const relativePath = normalizeWorkspaceRelativePath(sourcePath);
    if (!relativePath) {
        return undefined;
    }
    const absolutePath = path.resolve(workspaceRoot, relativePath);
    if (!isPathInside(absolutePath, workspaceRoot) || !fs.existsSync(absolutePath)) {
        return undefined;
    }
    try {
        const realWorkspace = fs.realpathSync(workspaceRoot);
        const realSource = fs.realpathSync(absolutePath);
        return isPathInside(realSource, realWorkspace) ? realSource : undefined;
    } catch {
        return undefined;
    }
}

function openMarkdownPreview(absolutePath: string): void {
    if (!fs.existsSync(absolutePath)) {
        vscode.window.showWarningMessage(`Wiki page not found: ${absolutePath}`);
        return;
    }
    vscode.commands.executeCommand('markdown.showPreview', vscode.Uri.file(absolutePath));
}

function runTerminalCommand(name: string, command: string, env?: Record<string, string>): void {
    try {
        ensureWorkspaceTrusted();
    } catch (error) {
        vscode.window.showErrorMessage(error instanceof Error ? error.message : String(error));
        return;
    }
    const workspaceRoot = getWorkspaceRoot();
    const terminal = vscode.window.createTerminal({ name, cwd: workspaceRoot, env });
    terminal.show();
    terminal.sendText(command);
}

function renderNavigationTree(nodes: NavigationTreeNode[], files: WikiFile[]): string {
    const pageMap = new Map<string, WikiFile>();
    for (const file of files) {
        pageMap.set(file.relativePath, file);
    }
    return nodes.map((node, index) => renderTreeNode(node, index < 3, pageMap)).join('');
}

function renderTreeNode(node: NavigationTreeNode, open: boolean, pageMap: Map<string, WikiFile>): string {
    const label = escapeHtml(pickString(node.label) ?? '(unnamed)');
    const children = Array.isArray(node.children) ? node.children : [];
    if ((node.type ?? '').toLowerCase() === 'page' && node.path) {
        const normalizedPath = normalizeReleasePageRelativePath(node.path);
        const file = normalizedPath ? pageMap.get(normalizedPath) : undefined;
        if (!file) {
            return '';
        }
        const id = escapeHtml(file.id);
        const title = escapeHtml(file.relativePath);
        const displayLabel = file.label;
        return `<button class="node ${getNodeType(node.path)}" data-id="${id}" title="${title}">${escapeHtml(displayLabel)}</button>`;
    }

    if (children.length === 0) {
        return '';
    }

    const childHtml = children.map((child) => renderTreeNode(child, false, pageMap)).join('');
    return `
        <details ${open ? 'open' : ''}>
            <summary>${label}</summary>
            <div class="children">${childHtml}</div>
        </details>
    `;
}

function buildPageKey(filePath: string): string {
    return normalizeSlashPath(filePath);
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
        .provenance {
            margin-top: 10px;
            font-size: 11px;
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
        .related {
            border-bottom: 1px solid var(--border);
            margin-bottom: 10px;
            padding-bottom: 10px;
        }
        .related ul {
            list-style: none;
            margin: 0 0 10px;
            padding: 0;
        }
        .related li {
            display: flex;
            flex-direction: column;
            gap: 2px;
            padding: 4px 0;
        }
        .related small {
            color: var(--muted);
            font-size: 10px;
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
    const citationMapElement = document.getElementById('repoWikiCitationMap');
    const citationMap = citationMapElement ? JSON.parse(citationMapElement.textContent || '{}') : {};
    document.addEventListener('click', (event) => {
        const target = event.target instanceof Element ? event.target : null;
        if (!target) return;
        const pageControl = target.closest('[data-id]');
        if (pageControl && pageControl instanceof HTMLElement && pageControl.dataset.id) {
            vscode.postMessage({ command: 'openPage', id: pageControl.dataset.id });
            return;
        }
        const citationControl = target.closest('[data-citation-id]');
        if (citationControl && citationControl instanceof HTMLElement && citationControl.dataset.citationId) {
            const citation = citationMap[citationControl.dataset.citationId];
            if (citation) {
                vscode.postMessage({ command: 'openSourceCitation', citation });
            }
            return;
        }
        const commandControl = target.closest('[data-command]');
        if (commandControl && commandControl instanceof HTMLElement && commandControl.dataset.command) {
            vscode.postMessage({ command: commandControl.dataset.command });
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
