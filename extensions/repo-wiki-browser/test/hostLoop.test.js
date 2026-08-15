'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const hostLoop = require('../out/hostLoop');

function withDir(fn) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'repo-wiki-ready-gap-'));
    try {
        fn(dir);
    } finally {
        fs.rmSync(dir, { recursive: true, force: true });
    }
}

function writeJson(filePath, value) {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, JSON.stringify(value), 'utf8');
}

function testDiagnoseNotGenerated() {
    withDir((root) => {
        const result = hostLoop.diagnoseReadyGap(root);
        assert.strictEqual(result.kind, 'not_generated');
        assert.strictEqual(result.nextAction, 'generate');
        assert.ok(result.nextCommand.includes('--output .repo-agent-eval'));
        assert.ok(result.nextCommand.includes('generate'));
    });
}

function testDiagnoseVerifyFailed() {
    withDir((root) => {
        writeJson(path.join(root, '.repo-agent-eval', 'runs', 'run-a', 'manifest.json'), {
            run_id: 'run-a',
            readiness_state: 'NOT_READY',
        });
        writeJson(path.join(root, '.repo-agent-eval', 'runs', 'run-a', 'reports', 'strict-verify-output.json'), {
            grade: 'FAIL',
            status: 'NOT_READY',
            hard_gate_codes: ['QODER_CONTENT_EMPTY'],
            summary: { hard_gate_failures: 1 },
            gate_summary: { hard_gate_blocking: true },
        });
        const result = hostLoop.diagnoseReadyGap(root);
        assert.strictEqual(result.kind, 'verify_failed');
        assert.strictEqual(result.nextAction, 'verify');
        assert.strictEqual(result.runId, 'run-a');
        assert.ok(String(result.failureReason).includes('QODER_CONTENT_EMPTY'));
        assert.ok(result.nextCommand.includes('verify'));
        assert.ok(result.nextCommand.includes('--output .repo-agent-eval'));
    });
}

function testDiagnoseNotPublishedAfterVerifyPass() {
    withDir((root) => {
        writeJson(path.join(root, '.repo-agent-eval', 'runs', 'run-b', 'manifest.json'), {
            run_id: 'run-b',
            readiness_state: 'READY',
        });
        writeJson(path.join(root, '.repo-agent-eval', 'runs', 'run-b', 'reports', 'strict-verify-output.json'), {
            grade: 'PASS',
            status: 'READY',
            hard_gate_codes: [],
            summary: { hard_gate_failures: 0 },
        });
        const result = hostLoop.diagnoseReadyGap(root);
        assert.strictEqual(result.kind, 'not_published');
        assert.strictEqual(result.nextAction, 'publish');
        assert.strictEqual(result.nextCommand, hostLoop.DEFAULT_PUBLISH_COMMAND);
        assert.ok(result.nextCommand.includes('release-publish'));
        assert.ok(result.nextCommand.includes('--output .repo-agent-eval'));
    });
}

function testDiagnoseGeneratedButNotVerified() {
    withDir((root) => {
        writeJson(path.join(root, '.repo-agent-eval', 'runs', 'run-c', 'manifest.json'), {
            run_id: 'run-c',
        });
        const result = hostLoop.diagnoseReadyGap(root);
        assert.strictEqual(result.kind, 'not_verified');
        assert.strictEqual(result.nextAction, 'verify');
        assert.ok(result.nextCommand.includes('verify --profile qoder-like --ci --output .repo-agent-eval'));
    });
}

function testDiagnoseReadyRelease() {
    withDir((root) => {
        writeJson(path.join(root, '.repo-agent-eval', 'repowiki', 'zh', 'manifest.json'), {
            release_status: 'READY',
            navigation_tree: [{ type: 'page', label: 'Overview', path: 'content/00-overview.md' }],
        });
        const result = hostLoop.diagnoseReadyGap(root);
        assert.strictEqual(result.kind, 'ready');
        assert.strictEqual(result.nextAction, 'none');
    });
}

function testDiagnoseEmptyNavigation() {
    withDir((root) => {
        writeJson(path.join(root, '.repo-agent-eval', 'repowiki', 'zh', 'manifest.json'), {
            readiness_state: 'READY',
            navigation_tree: [],
        });
        const result = hostLoop.diagnoseReadyGap(root);
        assert.strictEqual(result.kind, 'empty_navigation');
        assert.strictEqual(result.nextAction, 'publish');
    });
}

function testSummarizeCliFailureFromJson() {
    const output = [
        'generating pages',
        JSON.stringify({
            grade: 'FAIL',
            status: 'NOT_READY',
            hard_gate_codes: ['QODER_MANIFEST_NOT_READY'],
            error: 'strict verify failed',
        }, null, 2),
    ].join('\n');
    const summary = hostLoop.summarizeCliOutput(output, 1);
    assert.ok(summary.progressText);
    assert.ok(String(summary.failureReason).includes('QODER_MANIFEST_NOT_READY'));
}

function testSummarizeCliSuccessUsesLastLine() {
    const summary = hostLoop.summarizeCliOutput('indexing\nWrote manifest.json\n', 0);
    assert.strictEqual(summary.progressText, 'Wrote manifest.json');
    assert.strictEqual(summary.failureReason, undefined);
}

function testIsolationCommands() {
    assert.strictEqual(
        hostLoop.DEFAULT_GENERATE_COMMAND,
        'uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval',
    );
    assert.strictEqual(
        hostLoop.DEFAULT_VERIFY_COMMAND,
        'uv run repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval',
    );
    assert.strictEqual(
        hostLoop.DEFAULT_PUBLISH_COMMAND,
        'uv run repo-wiki release-publish --output .repo-agent-eval',
    );
}

const tests = [
    testDiagnoseNotGenerated,
    testDiagnoseVerifyFailed,
    testDiagnoseNotPublishedAfterVerifyPass,
    testDiagnoseGeneratedButNotVerified,
    testDiagnoseReadyRelease,
    testDiagnoseEmptyNavigation,
    testSummarizeCliFailureFromJson,
    testSummarizeCliSuccessUsesLastLine,
    testIsolationCommands,
];

let failed = 0;
for (const test of tests) {
    try {
        test();
        console.log(`PASS ${test.name}`);
    } catch (error) {
        failed += 1;
        console.error(`FAIL ${test.name}`);
        console.error(error);
    }
}

if (failed) {
    process.exit(1);
}
console.log(`PASS ${tests.length} hostLoop contract tests`);
