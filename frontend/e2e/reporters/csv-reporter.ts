import fs from "node:fs";
import path from "node:path";

import type {
  Reporter,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";

interface CsvReporterOptions {
  outputFile?: string;
}

interface Row {
  timestamp: string;
  specFile: string;
  scenario: string;
  testTitle: string;
  browser: string;
  status: string;
  durationMs: number;
  retries: number;
  errorMessage: string;
  trace: string;
  video: string;
}

const HEADERS = [
  "timestamp",
  "spec_file",
  "scenario",
  "test_title",
  "browser",
  "status",
  "duration_ms",
  "retries",
  "error_message",
  "trace",
  "video",
];

function csvCell(value: string | number | null | undefined): string {
  const s = value == null ? "" : String(value);
  return `"${s.replace(/"/g, '""').replace(/\r?\n/g, " ")}"`;
}

function attachmentPath(result: TestResult, name: string): string {
  return result.attachments.find((a) => a.name === name)?.path ?? "";
}

/**
 * Minimal Playwright reporter that flattens every test into one CSV row, so
 * the E2E layer can be merged with backend/chaos results by
 * scripts/collect-results.py.
 */
export default class CsvReporter implements Reporter {
  private readonly rows: Row[] = [];
  private readonly outputFile: string;

  constructor(options: CsvReporterOptions = {}) {
    this.outputFile =
      options.outputFile ??
      path.resolve(process.cwd(), "..", "test-reports", "e2e-results.csv");
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const titlePath = test.titlePath().filter(Boolean);
    this.rows.push({
      timestamp: new Date().toISOString(),
      specFile: path.basename(test.location.file),
      scenario: titlePath.length > 1 ? titlePath[1] : titlePath[0] ?? "",
      testTitle: test.title,
      browser: test.parent.project()?.name ?? "",
      status: result.status,
      durationMs: result.duration,
      retries: result.retry,
      errorMessage: result.error?.message ?? "",
      trace: attachmentPath(result, "trace"),
      video: attachmentPath(result, "video"),
    });
  }

  onEnd(): void {
    fs.mkdirSync(path.dirname(this.outputFile), { recursive: true });
    const lines = [HEADERS.join(",")];
    for (const r of this.rows) {
      lines.push(
        [
          csvCell(r.timestamp),
          csvCell(r.specFile),
          csvCell(r.scenario),
          csvCell(r.testTitle),
          csvCell(r.browser),
          csvCell(r.status),
          csvCell(r.durationMs),
          csvCell(r.retries),
          csvCell(r.errorMessage),
          csvCell(r.trace),
          csvCell(r.video),
        ].join(",")
      );
    }
    fs.writeFileSync(this.outputFile, lines.join("\n") + "\n", "utf-8");
    console.log(`\n[e2e-csv] wrote ${this.rows.length} rows -> ${this.outputFile}`);
  }
}
