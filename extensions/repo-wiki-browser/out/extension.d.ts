import * as vscode from 'vscode';
export declare function activate(context: vscode.ExtensionContext): void;
export declare function deactivate(): void;
export declare function safeResolveReleasePagePath(contentDir: string, candidatePath: string, workspaceRoot?: string, releaseRoot?: string, manifestPath?: string): {
    absolutePath: string;
    relativePath: string;
} | undefined;
interface SourceCitation {
    sourcePath: string;
    startLine?: number;
    endLine?: number;
}
export declare function parseSourceCitation(citation: unknown): SourceCitation | undefined;
export {};
//# sourceMappingURL=extension.d.ts.map