import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const SNAPSHOT_STORE_KEY = "tds_scan_snapshots_v1";

const DEFAULT_EVALUATION_METRICS = [
  {
    id: "sonar_precision",
    title: "Code smell detection precision vs. SonarQube baseline",
    description:
      "Reported smells are benchmarked against a SonarQube ruleset on representative corpora; precision and recall targets are tracked release-over-release.",
  },
  {
    id: "acceptance_rate",
    title: "Refactoring suggestion acceptance rate (human-rated)",
    description:
      "Blind reviews score suggested after snippets for usefulness; acceptance rate guides prompt and heuristic tuning.",
  },
  {
    id: "scan_latency",
    title: "Scan completion time for 10k-line codebase",
    description:
      "End-to-end scan duration on a standardized ~10k LOC tree (excluding vendor) is measured in CI for regressions.",
  },
];

function scoreTone(score) {
  if (score >= 80) return "good";
  if (score >= 50) return "warn";
  return "risk";
}

function complexityTone(cc) {
  if (cc <= 15) return "good";
  if (cc <= 30) return "warn";
  return "risk";
}

function parseApiError(data) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "string" ? item : item?.msg || JSON.stringify(item)))
      .join("; ");
  }
  return "Scan failed.";
}

function totalSmellsFromSnapshot(snap) {
  if (snap?.summary?.total_smells != null) return snap.summary.total_smells;
  return Object.values(snap?.file_index || {}).reduce((n, x) => n + (x.smells || 0), 0);
}

function compareSnapshots(prev, curr) {
  const smellPrev = totalSmellsFromSnapshot(prev);
  const smellCurr =
    curr.summary?.total_smells ?? (curr.files || []).reduce((n, f) => n + (f.smells?.length ?? 0), 0);
  const prevIdx = prev.file_index || {};
  const fileChanges = [];
  for (const f of curr.files || []) {
    const p = prevIdx[f.file];
    if (p && p.score !== f.file_score) {
      fileChanges.push({ file: f.file, before: p.score, after: f.file_score, delta: f.file_score - p.score });
    }
  }
  return {
    overall_delta: curr.overall_score - prev.overall_score,
    smells_delta: smellCurr - smellPrev,
    files_delta: (curr.summary?.files_analyzed ?? 0) - (prev.summary?.files_analyzed ?? 0),
    duration_delta_ms: (curr.scan_meta?.analysis_duration_ms ?? 0) - (prev.scan_meta?.analysis_duration_ms ?? 0),
    fileChanges,
  };
}

function persistAndCompareSnapshot(sourceKey, data) {
  let store = {};
  try {
    store = JSON.parse(localStorage.getItem(SNAPSHOT_STORE_KEY) || "{}");
  } catch {
    store = {};
  }
  const prev = store[sourceKey] || null;
  const trend = prev ? compareSnapshots(prev, data) : null;
  store[sourceKey] = {
    overall_score: data.overall_score,
    summary: data.summary,
    scan_meta: data.scan_meta,
    file_index: Object.fromEntries(
      (data.files || []).map((f) => [f.file, { score: f.file_score, smells: f.smells?.length ?? 0 }]),
    ),
    files: data.files,
  };
  try {
    localStorage.setItem(SNAPSHOT_STORE_KEY, JSON.stringify(store));
  } catch {
    /* quota */
  }
  return trend;
}

function useMouseTilt() {
  useEffect(() => {
    const onMove = (event) => {
      const mx = event.clientX / window.innerWidth;
      const my = event.clientY / window.innerHeight;
      document.documentElement.style.setProperty("--mx", String(mx));
      document.documentElement.style.setProperty("--my", String(my));
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);
}

function App() {
  const [file, setFile] = useState(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [sensitivity, setSensitivity] = useState("balanced");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [entered, setEntered] = useState(false);
  const [trend, setTrend] = useState(null);
  const [evaluationMetrics, setEvaluationMetrics] = useState(DEFAULT_EVALUATION_METRICS);
  const [referenceCatalog, setReferenceCatalog] = useState([]);
  const [catalogOpen, setCatalogOpen] = useState(true);

  useMouseTilt();

  useEffect(() => {
    const id = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mRes, cRes] = await Promise.all([
          fetch(`${API_BASE}/evaluation-metrics`),
          fetch(`${API_BASE}/smell-catalog`),
        ]);
        const mJson = await mRes.json();
        const cJson = await cRes.json();
        if (!cancelled) {
          if (Array.isArray(mJson)) setEvaluationMetrics(mJson);
          if (Array.isArray(cJson)) setReferenceCatalog(cJson);
        }
      } catch {
        /* offline API */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const sortedFiles = useMemo(() => {
    if (!result?.files) return [];
    return [...result.files].sort((a, b) => a.file_score - b.file_score);
  }, [result]);

  const runScan = async (mode) => {
    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      let endpoint = "";
      let sourceKey = null;

      if (mode === "zip") {
        if (!file) throw new Error("Choose a ZIP file first.");
        formData.append("file", file);
        endpoint = "/scan-zip";
        sourceKey = file.name ? `zip:${file.name}` : null;
      } else {
        if (!repoUrl.trim()) throw new Error("Enter a repository URL.");
        formData.append("repo_url", repoUrl.trim());
        endpoint = "/scan-repo";
        sourceKey = `repo:${repoUrl.trim()}`;
      }
      formData.append("sensitivity", sensitivity);

      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) throw new Error(parseApiError(data));

      if (sourceKey) {
        const nextTrend = persistAndCompareSnapshot(sourceKey, data);
        setTrend(nextTrend);
      } else {
        setTrend(null);
      }

      setResult(data);
      if (Array.isArray(data.smell_catalog) && data.smell_catalog.length) {
        setReferenceCatalog(data.smell_catalog);
      }
      if (Array.isArray(data.evaluation_metrics) && data.evaluation_metrics.length) {
        setEvaluationMetrics(data.evaluation_metrics);
      }
    } catch (scanError) {
      setError(scanError.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const formatDelta = (n) => (n > 0 ? `+${n}` : String(n));

  return (
    <div className={`app-shell ${entered ? "app-shell--entered" : ""}`}>
      <div className="backdrop" aria-hidden>
        <div className="backdrop__void" />
        <div className="backdrop__corona" />
        <div className="backdrop__bloom backdrop__bloom--ember" />
        <div className="backdrop__bloom backdrop__bloom--sapphire" />
        <div className="backdrop__vault" />
        <div className="backdrop__grain" />
      </div>

      <main className="page">
        <div className="sovereign-header">
          <div className={`sovereign-rule sovereign-rule--top ${entered ? "sovereign-rule--on" : ""}`} />
          <header className={`hero slide-majesty slide-majesty--1 ${entered ? "slide-majesty--on" : ""}`}>
            <p className="eyebrow">Technical Debt Scorer</p>
            <h1 className="title">
              <span className="title__line">Sovereign clarity</span>
              <span className="title__line title__line--accent">over every line of code</span>
            </h1>
            <p className="subtitle">
              Present your archive or repository. The ledger lists LOC, cyclomatic complexity, catalogued smells with
              line references, and refactoring excerpts—optionally refined by an LLM when configured server-side.
            </p>
            <p className={`status ${loading ? "status--busy" : ""}`} aria-live="polite">
              {loading ? "The tally is in motion…" : "The hall responds to your gaze—tilt follows the cursor."}
            </p>
          </header>
          <div className={`sovereign-rule sovereign-rule--bottom ${entered ? "sovereign-rule--on" : ""}`} />
        </div>

        <section className="panel" aria-label="Scan inputs">
          <div className="sensitivity-control">
            <label htmlFor="debt-sensitivity">Debt sensitivity</label>
            <select
              id="debt-sensitivity"
              value={sensitivity}
              onChange={(event) => setSensitivity(event.target.value)}
              disabled={loading}
            >
              <option value="strict">Strict</option>
              <option value="balanced">Balanced</option>
              <option value="lenient">Lenient</option>
            </select>
          </div>
          <div className="inputs">
            <div className={`card-wrap card-wrap--a ${entered ? "card-wrap--on" : ""}`}>
              <div className="card-plate tilt">
                <div className="card-ornament card-ornament--tl" aria-hidden />
                <div className="card-ornament card-ornament--br" aria-hidden />
                <h2 className="card-title">ZIP archive</h2>
                <p className="card-desc">Deliver a sealed archive of your realm.</p>
                <input
                  type="file"
                  accept=".zip"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
                <button type="button" disabled={loading} onClick={() => runScan("zip")}>
                  {loading ? "Working…" : "Analyze ZIP"}
                </button>
              </div>
            </div>

            <div className={`card-wrap card-wrap--b ${entered ? "card-wrap--on" : ""}`}>
              <div className="card-plate tilt">
                <div className="card-ornament card-ornament--tl" aria-hidden />
                <div className="card-ornament card-ornament--br" aria-hidden />
                <h2 className="card-title">Git repository</h2>
                <p className="card-desc">Summon by HTTPS or SSH path.</p>
                <input
                  type="text"
                  placeholder="https://github.com/org/repo.git"
                  value={repoUrl}
                  onChange={(event) => setRepoUrl(event.target.value)}
                  autoComplete="off"
                />
                <button type="button" disabled={loading} onClick={() => runScan("repo")}>
                  {loading ? "Working…" : "Analyze repo"}
                </button>
              </div>
            </div>
          </div>

          <div className={`progress-track ${loading ? "progress-track--on" : ""}`}>
            <div className="progress-track__sheen" />
          </div>
          {error ? (
            <p className="error error--reveal" role="alert">
              {error}
            </p>
          ) : null}
        </section>

        {result ? (
          <section className="results results--vault" aria-label="Scan results">
            <div className="codex-heading">
              <span className="codex-heading__wing" />
              <h2 className="codex-heading__title">Assessment ledger</h2>
              <span className="codex-heading__wing codex-heading__wing--mirror" />
            </div>

            {result.scan_meta?.llm_refine_enabled ? (
              <p className="llm-banner">
                LLM refinement is enabled (OpenAI). Suggestions marked “Model-refined” override local templates.
              </p>
            ) : (
              <p className="llm-banner llm-banner--muted">
                Heuristic + excerpt mode. Set <code>OPENAI_API_KEY</code> on the server for model-refined after
                snippets.
              </p>
            )}
            <p className="status">
              Sensitivity mode: <strong>{result.scan_meta?.sensitivity || sensitivity}</strong>
            </p>

            {trend ? (
              <div className="trend-panel" role="region" aria-label="Comparison to previous scan">
                <h3 className="trend-panel__title">Compared to your last scan of this source</h3>
                <ul className="trend-panel__stats">
                  <li>
                    Technical Debt Scorer*:{" "}
                    <strong className={trend.overall_delta >= 0 ? "trend-up" : "trend-down"}>
                      {formatDelta(trend.overall_delta)}
                    </strong>
                  </li>
                  <li>
                    Total smells: <strong>{formatDelta(trend.smells_delta)}</strong>
                  </li>
                  <li>
                    Files analyzed: <strong>{formatDelta(trend.files_delta)}</strong>
                  </li>
                  <li>
                    Analysis time (ms): <strong>{formatDelta(trend.duration_delta_ms)}</strong>
                  </li>
                </ul>
                {trend.fileChanges.length ? (
                  <div className="trend-panel__files">
                    <p className="trend-panel__sub">Per-file score shifts</p>
                    <ul>
                      {trend.fileChanges.slice(0, 16).map((c) => (
                        <li key={c.file}>
                          <code>{c.file}</code>{" "}
                          <span className={c.delta >= 0 ? "trend-up" : "trend-down"}>
                            {c.before} → {c.after} ({formatDelta(c.delta)})
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="summary-row">
              <div className="summary-cell summary-cell--primary summary-cell--r1">
                <div className="summary-plate tilt">
                  <p className="label">Technical Debt Scorer*</p>
                  <p className={`summary-score ${scoreTone(result.overall_score)}`}>
                    {result.overall_score}
                    <span className="summary-score__max">/100</span>
                  </p>
                </div>
              </div>
              <div className="summary-cell summary-cell--r2">
                <div className="summary-plate tilt">
                  <p className="label">Files analyzed</p>
                  <p className="summary-value">{result.summary?.files_analyzed ?? result.files?.length ?? 0}</p>
                </div>
              </div>
              <div className="summary-cell summary-cell--r3">
                <div className="summary-plate tilt">
                  <p className="label">Total LOC</p>
                  <p className="summary-value">{result.summary?.total_loc ?? "—"}</p>
                </div>
              </div>
              <div className="summary-cell summary-cell--r4">
                <div className="summary-plate tilt">
                  <p className="label">Avg cyclomatic complexity</p>
                  <p className={`summary-value ${complexityTone(result.summary?.avg_cyclomatic_complexity ?? 0)}`}>
                    {result.summary?.avg_cyclomatic_complexity ?? "—"}
                  </p>
                </div>
              </div>
              <div className="summary-cell summary-cell--r5">
                <div className="summary-plate tilt">
                  <p className="label">Total smells</p>
                  <p className="summary-value">{result.summary?.total_smells ?? "—"}</p>
                </div>
              </div>
              <div className="summary-cell summary-cell--r6">
                <div className="summary-plate tilt">
                  <p className="label">Analysis time</p>
                  <p className="summary-value">
                    {result.scan_meta?.analysis_duration_ms != null
                      ? `${result.scan_meta.analysis_duration_ms} ms`
                      : "—"}
                  </p>
                </div>
              </div>
            </div>

            {result.summary?.files_analyzed === 0 ? (
              <div className="callout callout--warn chamber-callout" role="status">
                No supported source files were found (e.g. TypeScript, JavaScript, Python, Go, Rust, Java). Check that
                the repo is not only vendor or build output.
              </div>
            ) : null}

            <ul className="file-list">
              {sortedFiles.map((fileResult, index) => {
                const cc =
                  fileResult.metrics?.cyclomatic_complexity ??
                  fileResult.metrics?.cyclomatic_estimation ??
                  0;
                const ccPct = Math.min(100, (cc / 60) * 100);
                const phys = fileResult.metrics?.physical_lines;
                const fromWest = index % 2 === 0;
                return (
                  <li
                    key={fileResult.file}
                    className={`file-chamber ${fromWest ? "file-chamber--west" : "file-chamber--east"}`}
                    style={{ "--stagger": index }}
                  >
                    <div className="file-plate tilt">
                      <div className="file-head">
                        <div className="file-title-block">
                          <span className="file-path">{fileResult.file}</span>
                          {fileResult.language ? (
                            <span className="lang-tag">{fileResult.language}</span>
                          ) : null}
                        </div>
                        <span className={`pill ${scoreTone(fileResult.file_score)}`}>
                          {fileResult.file_score}/100
                        </span>
                      </div>

                      <div className="metrics-grid">
                        <div className="metric-cell">
                          <span className="metric-label">LOC (non-blank)</span>
                          <span className="metric-num">{fileResult.metrics.loc}</span>
                        </div>
                        {phys != null ? (
                          <div className="metric-cell">
                            <span className="metric-label">Lines (file)</span>
                            <span className="metric-num">{phys}</span>
                          </div>
                        ) : null}
                        <div className="metric-cell metric-cell--span">
                          <div className="metric-row">
                            <span className="metric-label">Cyclomatic complexity (est.)</span>
                            <span className={`metric-num ${complexityTone(cc)}`}>{cc}</span>
                          </div>
                          <div className="cc-track">
                            <div
                              className={`cc-fill ${complexityTone(cc)}`}
                              style={{ width: `${ccPct}%` }}
                            />
                          </div>
                          <p className="metric-note">Branches and paths approximated at file level.</p>
                        </div>
                      </div>

                      {fileResult.smells.length ? (
                        <ul className="smell-list">
                          {fileResult.smells.map((smell, smellIndex) => (
                            <li key={`${fileResult.file}-${smellIndex}`}>
                              <div className="smell-head">
                                <span className="smell-name">{smell.name}</span>
                                {smell.catalog_id ? (
                                  <span className="smell-catalog-id">{smell.catalog_id}</span>
                                ) : null}
                                {smell.line_reference ? (
                                  <span className="smell-lines">{smell.line_reference}</span>
                                ) : smell.line_start ? (
                                  <span className="smell-lines">
                                    L{smell.line_start}
                                    {smell.line_end && smell.line_end !== smell.line_start
                                      ? `–L${smell.line_end}`
                                      : ""}
                                  </span>
                                ) : null}
                                {smell.llm_refined ? (
                                  <span className="smell-llm">Model-refined</span>
                                ) : null}
                              </div>
                              <span className="smell-text">{smell.suggestion}</span>
                              {smell.explanation ? (
                                <span className="smell-detail">{smell.explanation}</span>
                              ) : null}
                              {smell.before ? (
                                <div className="code-block-wrap">
                                  <span className="code-block-label">Before (excerpt)</span>
                                  <pre className="code-block">
                                    <code>{smell.before}</code>
                                  </pre>
                                </div>
                              ) : null}
                              {smell.after ? (
                                <div className="code-block-wrap">
                                  <span className="code-block-label">After (refactor suggestion)</span>
                                  <pre className="code-block code-block--after">
                                    <code>{smell.after}</code>
                                  </pre>
                                </div>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="file-footnote">No issues flagged for this file.</p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}

        <footer className={`page-annex ${entered ? "page-annex--entered" : ""}`} aria-label="Reference and methodology">
          <div className={`page-annex__rule ${entered ? "page-annex__rule--on" : ""}`} />

          {referenceCatalog.length ? (
            <section className="annex-catalog" aria-label="Code smell catalog">
              <div className="annex-heading">
                <span className="annex-heading__ornament annex-heading__ornament--left" aria-hidden />
                <div className="annex-heading__center">
                  <p className="annex-heading__eyebrow">Reference</p>
                  <h2 className="annex-heading__title">Code smell catalog</h2>
                  <p className="annex-heading__sub">Formal definitions aligned with scan findings</p>
                </div>
                <span className="annex-heading__ornament annex-heading__ornament--right" aria-hidden />
              </div>

              <button
                type="button"
                className="annex-catalog__drawer"
                onClick={() => setCatalogOpen((o) => !o)}
                aria-expanded={catalogOpen}
              >
                <span className="annex-catalog__drawer-label">{catalogOpen ? "Collapse codex" : "Expand codex"}</span>
                <span className="annex-catalog__drawer-line" aria-hidden />
                <span className={`annex-catalog__drawer-chev ${catalogOpen ? "is-open" : ""}`} aria-hidden>
                  ◆
                </span>
              </button>

              {catalogOpen ? (
                <div className="annex-catalog__grid">
                  {referenceCatalog.map((entry) => (
                    <article key={entry.catalog_id} className="annex-catalog-card tilt">
                      <header className="annex-catalog-card__head">
                        <span className="annex-catalog-card__id">{entry.catalog_id}</span>
                        <span className="annex-catalog-card__category">{entry.category}</span>
                      </header>
                      <h3 className="annex-catalog-card__name">{entry.name}</h3>
                      <p className="annex-catalog-card__desc">{entry.description}</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}

          {evaluationMetrics?.length ? (
            <section className="annex-metrics" aria-label="Evaluation metrics">
              <div className="annex-heading annex-heading--metrics">
                <span className="annex-heading__ornament annex-heading__ornament--left" aria-hidden />
                <div className="annex-heading__center">
                  <p className="annex-heading__eyebrow">Methodology</p>
                  <h2 className="annex-heading__title">Evaluation metrics</h2>
                  <p className="annex-heading__sub">How the instrument itself is measured—not your project score</p>
                </div>
                <span className="annex-heading__ornament annex-heading__ornament--right" aria-hidden />
              </div>

              <ol className="annex-metrics__list">
                {evaluationMetrics.map((item, index) => (
                  <li key={item.id} className="annex-metrics__item">
                    <span className="annex-metrics__index" aria-hidden>
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div className="annex-metrics__body">
                      <h3 className="annex-metrics__title">{item.title}</h3>
                      <p className="annex-metrics__desc">{item.description}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
        </footer>
      </main>
    </div>
  );
}

export default App;
