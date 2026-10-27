export declare const EVAL_OUTPUT = ".repo-agent-eval";
export declare const DEFAULT_GENERATE_COMMAND = "uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval";
export declare const DEFAULT_VERIFY_COMMAND = "uv run repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval";
export declare const DEFAULT_PUBLISH_COMMAND = "uv run repo-wiki release-publish --output .repo-agent-eval";
export type ReadyGapKind = 'ready' | 'not_generated' | 'not_verified' | 'verify_failed' | 'not_published' | 'release_not_ready' | 'empty_navigation';
export type ReadyGapAction = 'generate' | 'verify' | 'publish' | 'none';
export interface ReadyGapDiagnosis {
    kind: ReadyGapKind;
    nextAction: ReadyGapAction;
    nextCommand: string;
    runId?: string;
    failureReason?: string;
    hardGateCodes?: string[];
}
export interface CliOutputSummary {
    progressText: string;
    failureReason?: string;
}
export declare function pickReleaseReadyString(manifest: Record<string, unknown>): string | undefined;
export declare function diagnoseReadyGap(workspaceRoot: string): ReadyGapDiagnosis;
export declare function extractLastJsonObject(text: string): Record<string, unknown> | undefined;
export declare function summarizeCliOutput(combined: string, exitCode: number | null): CliOutputSummary;
export declare function readyGapCopy(diagnosis: ReadyGapDiagnosis, locale: string): {
    title: string;
    detail: string;
};
//# sourceMappingURL=hostLoop.d.ts.map