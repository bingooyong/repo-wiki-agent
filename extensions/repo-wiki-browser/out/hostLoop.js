"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_PUBLISH_COMMAND = exports.DEFAULT_VERIFY_COMMAND = exports.DEFAULT_GENERATE_COMMAND = exports.EVAL_OUTPUT = void 0;
exports.pickReleaseReadyString = pickReleaseReadyString;
exports.diagnoseReadyGap = diagnoseReadyGap;
exports.extractLastJsonObject = extractLastJsonObject;
exports.summarizeCliOutput = summarizeCliOutput;
exports.readyGapCopy = readyGapCopy;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
exports.EVAL_OUTPUT = '.repo-agent-eval';
exports.DEFAULT_GENERATE_COMMAND = 'uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval';
exports.DEFAULT_VERIFY_COMMAND = 'uv run repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval';
exports.DEFAULT_PUBLISH_COMMAND = 'uv run repo-wiki release-publish --output .repo-agent-eval';
function pickString(value) {
    return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined;
}
function pickReleaseReadyString(manifest) {
    const direct = pickString(manifest.release_status) ??
        pickString(manifest.readiness_state) ??
        pickString(manifest.readiness);
    if (direct) {
        return direct;
    }
    const nested = manifest.readiness;
    if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
        const r = nested;
        return pickString(r.readiness_state) ?? pickString(r.status);
    }
    return undefined;
}
function readJsonObject(filePath) {
    try {
        const raw = fs.readFileSync(filePath, 'utf8');
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
            ? parsed
            : undefined;
    }
    catch {
        return undefined;
    }
}
function navigationTree(manifest) {
    return Array.isArray(manifest.navigation_tree) ? manifest.navigation_tree : undefined;
}
function discoverEvalRuns(workspaceRoot) {
    const evalRoot = path.join(workspaceRoot, exports.EVAL_OUTPUT);
    if (!fs.existsSync(evalRoot)) {
        return [];
    }
    const runs = [];
    const seen = new Set();
    const addRun = (runDir, fallbackId) => {
        const manifestPath = path.join(runDir, 'manifest.json');
        if (!fs.existsSync(manifestPath)) {
            return;
        }
        const realKey = path.resolve(runDir);
        if (seen.has(realKey)) {
            return;
        }
        const manifest = readJsonObject(manifestPath);
        if (!manifest) {
            return;
        }
        seen.add(realKey);
        const runId = pickString(manifest.run_id) ?? fallbackId;
        const verifyPath = path.join(runDir, 'reports', 'strict-verify-output.json');
        runs.push({
            runId,
            runDir,
            manifest,
            verifyReport: fs.existsSync(verifyPath) ? readJsonObject(verifyPath) : undefined,
        });
    };
    const runsBucket = path.join(evalRoot, 'runs');
    if (fs.existsSync(runsBucket) && fs.statSync(runsBucket).isDirectory()) {
        for (const entry of fs.readdirSync(runsBucket).sort()) {
            if (entry.startsWith('.')) {
                continue;
            }
            const candidate = path.join(runsBucket, entry);
            if (fs.statSync(candidate).isDirectory()) {
                addRun(candidate, entry);
            }
        }
    }
    for (const entry of fs.readdirSync(evalRoot).sort()) {
        if (entry.startsWith('.') || entry === 'repowiki' || entry === 'runs') {
            continue;
        }
        const candidate = path.join(evalRoot, entry);
        if (fs.statSync(candidate).isDirectory()) {
            addRun(candidate, entry);
        }
    }
    runs.sort((a, b) => a.runId.localeCompare(b.runId));
    return runs;
}
function asStringList(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.map((item) => pickString(item)).filter((item) => Boolean(item));
}
function isVerifyFailed(report) {
    if (!report) {
        return false;
    }
    const grade = (pickString(report.grade) ?? '').toUpperCase();
    const status = (pickString(report.status) ?? '').toUpperCase();
    const summary = report.summary && typeof report.summary === 'object' && !Array.isArray(report.summary)
        ? report.summary
        : undefined;
    const gate = report.gate_summary && typeof report.gate_summary === 'object' && !Array.isArray(report.gate_summary)
        ? report.gate_summary
        : undefined;
    const hardFailures = typeof summary?.hard_gate_failures === 'number' ? summary.hard_gate_failures : 0;
    const codes = asStringList(report.hard_gate_codes);
    return grade === 'FAIL'
        || status === 'NOT_READY'
        || hardFailures > 0
        || gate?.hard_gate_blocking === true
        || codes.length > 0;
}
function isVerifyPassed(report) {
    if (!report) {
        return false;
    }
    const grade = (pickString(report.grade) ?? '').toUpperCase();
    return grade === 'PASS' && !isVerifyFailed(report);
}
function verifyFailureReason(report) {
    if (!report) {
        return undefined;
    }
    const codes = asStringList(report.hard_gate_codes);
    if (codes.length > 0) {
        return codes.join(', ');
    }
    return pickString(report.error)
        ?? pickString(report.message)
        ?? pickString(report.grade)
        ?? pickString(report.status);
}
function diagnoseReadyGap(workspaceRoot) {
    const releaseManifestPath = path.join(workspaceRoot, exports.EVAL_OUTPUT, 'repowiki', 'zh', 'manifest.json');
    const releaseManifest = fs.existsSync(releaseManifestPath) ? readJsonObject(releaseManifestPath) : undefined;
    const releaseStatus = releaseManifest ? (pickReleaseReadyString(releaseManifest) ?? '').toUpperCase() : '';
    const nav = releaseManifest ? navigationTree(releaseManifest) : undefined;
    if (releaseManifest && releaseStatus === 'READY' && nav && nav.length > 0) {
        return { kind: 'ready', nextAction: 'none', nextCommand: '' };
    }
    if (releaseManifest && releaseStatus === 'READY') {
        return {
            kind: 'empty_navigation',
            nextAction: 'publish',
            nextCommand: exports.DEFAULT_PUBLISH_COMMAND,
        };
    }
    const runs = discoverEvalRuns(workspaceRoot);
    const latest = runs.length > 0 ? runs[runs.length - 1] : undefined;
    if (latest && isVerifyFailed(latest.verifyReport)) {
        return {
            kind: 'verify_failed',
            nextAction: 'verify',
            nextCommand: exports.DEFAULT_VERIFY_COMMAND,
            runId: latest.runId,
            failureReason: verifyFailureReason(latest.verifyReport),
            hardGateCodes: asStringList(latest.verifyReport?.hard_gate_codes),
        };
    }
    if (latest && isVerifyPassed(latest.verifyReport)) {
        return {
            kind: 'not_published',
            nextAction: 'publish',
            nextCommand: exports.DEFAULT_PUBLISH_COMMAND,
            runId: latest.runId,
        };
    }
    if (latest) {
        return {
            kind: 'not_verified',
            nextAction: 'verify',
            nextCommand: exports.DEFAULT_VERIFY_COMMAND,
            runId: latest.runId,
        };
    }
    if (releaseManifest) {
        return {
            kind: 'release_not_ready',
            nextAction: 'publish',
            nextCommand: exports.DEFAULT_PUBLISH_COMMAND,
            failureReason: releaseStatus || 'unknown',
        };
    }
    return {
        kind: 'not_generated',
        nextAction: 'generate',
        nextCommand: exports.DEFAULT_GENERATE_COMMAND,
    };
}
function extractLastJsonObject(text) {
    let cursor = text.lastIndexOf('{');
    let attempts = 0;
    while (cursor >= 0 && attempts < 8) {
        attempts += 1;
        const slice = text.slice(cursor).trim();
        try {
            const parsed = JSON.parse(slice);
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                return parsed;
            }
        }
        catch {
            // Keep scanning earlier objects; CLI output often has nested braces.
        }
        cursor = text.lastIndexOf('{', cursor - 1);
    }
    return undefined;
}
function lastNonEmptyLine(text) {
    const lines = text.split(/\r?\n/).map((line) => line.trim()).filter((line) => line.length > 0);
    return lines.length > 0 ? lines[lines.length - 1].slice(0, 500) : '';
}
function summarizeCliOutput(combined, exitCode) {
    const progressText = lastNonEmptyLine(combined);
    const payload = extractLastJsonObject(combined);
    let failureReason;
    if (payload) {
        const codes = asStringList(payload.hard_gate_codes);
        if (codes.length > 0) {
            failureReason = codes.join(', ');
        }
        else {
            failureReason = pickString(payload.error)
                ?? pickString(payload.message)
                ?? (isVerifyFailed(payload) ? (pickString(payload.grade) ?? pickString(payload.status)) : undefined);
        }
    }
    if (exitCode !== null && exitCode !== 0) {
        failureReason = failureReason || progressText || `Command exited with code ${exitCode}`;
        return { progressText, failureReason };
    }
    return { progressText, failureReason: undefined };
}
function readyGapCopy(diagnosis, locale) {
    const en = locale === 'en';
    switch (diagnosis.kind) {
        case 'ready':
            return {
                title: en ? 'READY Wiki available' : '已发布 READY Wiki',
                detail: en ? 'Sidebar is reading the published release.' : '侧栏正在读取已发布的 READY release。',
            };
        case 'not_generated':
            return {
                title: en ? 'Wiki has not been generated' : '尚未生成 Wiki',
                detail: en
                    ? 'No qoder-like run exists under .repo-agent-eval. Generate first.'
                    : '`.repo-agent-eval` 下还没有 qoder-like run。请先生成。',
            };
        case 'not_verified':
            return {
                title: en ? 'Generated, not verified' : '已生成但尚未验证',
                detail: en
                    ? `Run ${diagnosis.runId ?? '(latest)'} exists, but strict verify has not passed.`
                    : `已有 run ${diagnosis.runId ?? '（最新）'}，但尚未通过严格验证。`,
            };
        case 'verify_failed':
            return {
                title: en ? 'Verification failed' : '验证未通过',
                detail: en
                    ? `Run ${diagnosis.runId ?? '(latest)'} failed HARD/SOFT gates: ${diagnosis.failureReason ?? 'see verify output'}.`
                    : `run ${diagnosis.runId ?? '（最新）'} 未通过门禁：${diagnosis.failureReason ?? '见验证输出'}。`,
            };
        case 'not_published':
            return {
                title: en ? 'Verified, not published' : '已验证但尚未发布 READY',
                detail: en
                    ? `Run ${diagnosis.runId ?? '(latest)'} passed verify. Publish it to .repo-agent-eval/repowiki/zh.`
                    : `run ${diagnosis.runId ?? '（最新）'} 已验证通过。发布后侧栏才能浏览 READY Wiki。`,
            };
        case 'release_not_ready':
            return {
                title: en ? 'Release exists but is not READY' : '发布目录存在但不是 READY',
                detail: en
                    ? `Found a release manifest with status ${diagnosis.failureReason ?? 'unknown'}.`
                    : `找到 release manifest，状态为 ${diagnosis.failureReason ?? 'unknown'}。`,
            };
        case 'empty_navigation':
            return {
                title: en ? 'READY but navigation_tree is empty' : 'READY 但 navigation_tree 为空',
                detail: en
                    ? 'The release cannot be browsed until navigation_tree is published.'
                    : '没有 navigation_tree 时侧栏无法浏览，请重新发布。',
            };
    }
}
//# sourceMappingURL=hostLoop.js.map