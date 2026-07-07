"use client";

import { useCallback, useRef, useState } from "react";
import { uploadDrawing } from "@/lib/api";
import { useJobPolling } from "@/hooks/useJobPolling";
import type { MTOResult } from "@/lib/schema";

// ── Inline minimal components for Sprint 0 ──────────────────────────────────
// Full polished components come in Sprint 7 & 8.

const ACCEPTED = ["image/png", "image/jpeg", "image/jpg", "application/pdf"];
const MAX_MB = 20;

type AppState = "idle" | "uploading" | "processing" | "results" | "error";

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { state: pollState, result, error: pollError, startPolling, reset } = useJobPolling();

  // Sync polling state → app state
  const prevPollState = useRef(pollState);
  if (prevPollState.current !== pollState) {
    prevPollState.current = pollState;
    if (pollState === "completed") {
      // Load the server-processed PNG (critical for PDFs since browser can't render them natively)
      setPreviewUrl(`http://localhost:8000/api/mto/${jobId}/image`);
      setAppState("results");
    }
    if (pollState === "failed") {
      setUploadError(pollError || "Processing failed");
      setAppState("error");
    }
  }

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED.includes(file.type)) return `Invalid file type. Accepted: PNG, JPG, PDF`;
    if (file.size > MAX_MB * 1024 * 1024) return `File too large. Max ${MAX_MB} MB`;
    return null;
  };

  const handleFile = useCallback(
    async (file: File) => {
      const err = validateFile(file);
      if (err) { setUploadError(err); return; }

      setUploadError(null);
      setCurrentFile(file);
      reset();

      // Preview
      if (file.type !== "application/pdf") {
        setPreviewUrl(URL.createObjectURL(file));
      } else {
        setPreviewUrl(null);
      }

      // Upload
      setAppState("uploading");
      setUploadProgress(0);
      try {
        // Fake progress animation while uploading
        const prog = setInterval(() => setUploadProgress((p) => Math.min(p + 10, 90)), 200);
        const res = await uploadDrawing(file);
        clearInterval(prog);
        setUploadProgress(100);
        setJobId(res.job_id);
        sessionStorage.setItem("lastJobId", res.job_id);

        // Start polling
        setAppState("processing");
        startPolling(res.job_id);
      } catch (e) {
        setUploadError(e instanceof Error ? e.message : "Upload failed");
        setAppState("error");
      }
    },
    [reset, startPolling]
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  const handleReset = () => {
    setAppState("idle");
    setUploadError(null);
    setPreviewUrl(null);
    setCurrentFile(null);
    setJobId(null);
    setUploadProgress(0);
    reset();
  };

  return (
    <main style={{ position: "relative", zIndex: 1 }}>
      {/* ── Header ── */}
      <header style={{ borderBottom: "1px solid var(--border)", padding: "1rem 0" }}>
        <div className="container flex items-center justify-between">
          <div className="flex items-center gap-sm">
            <span style={{ fontSize: "1.5rem" }}>⚙️</span>
            <div>
              <h1 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                PathNovo MTO Generator
              </h1>
              <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.1rem" }}>
                Isometric Drawing → AI Material Take-Off
              </p>
            </div>
          </div>
          {appState !== "idle" && (
            <button className="btn btn-secondary" onClick={handleReset}>
              ↺ New Drawing
            </button>
          )}
        </div>
      </header>

      <div className="container" style={{ paddingTop: "2rem", paddingBottom: "4rem" }}>

        {/* ── Mock banner ── */}
        {result?.source === "mock" && (
          <div style={{
            background: "rgba(245,158,11,0.1)",
            border: "1px solid rgba(245,158,11,0.3)",
            borderRadius: "var(--radius-sm)",
            padding: "0.75rem 1rem",
            marginBottom: "1.5rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            fontSize: "0.85rem",
            color: "var(--warning)",
          }}>
            ⚠️ <strong>Mock mode:</strong>&nbsp;No Gemini API key configured — showing sample MTO data.
            Set <code>GEMINI_API_KEY</code> in <code>backend/.env</code> to enable real AI extraction.
          </div>
        )}

        {/* ── IDLE: Upload zone ── */}
        {(appState === "idle" || appState === "error") && (
          <div style={{ maxWidth: "680px", margin: "0 auto" }}>
            <div style={{ textAlign: "center", marginBottom: "2rem" }}>
              <h2 style={{ fontSize: "clamp(1.4rem,3vw,2rem)", fontWeight: 700 }}>
                Upload Your Isometric Drawing
              </h2>
              <p className="text-secondary" style={{ marginTop: "0.5rem" }}>
                PNG, JPG, or PDF · Max {MAX_MB} MB · AI extracts all piping materials
              </p>
            </div>

            <div
              id="upload-dropzone"
              className={`dropzone ${isDragging ? "active" : ""}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
            >
              <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>
                {isDragging ? "📂" : "📐"}
              </div>
              <p style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                {isDragging ? "Drop to analyse" : "Drag & drop your isometric drawing"}
              </p>
              <p className="text-muted" style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
                or <span style={{ color: "var(--accent-light)", textDecoration: "underline" }}>click to browse</span>
              </p>
              <input
                ref={fileInputRef}
                id="file-input"
                type="file"
                accept=".png,.jpg,.jpeg,.pdf"
                style={{ display: "none" }}
                onChange={handleInputChange}
              />
            </div>

            {uploadError && (
              <div style={{
                marginTop: "1rem",
                padding: "0.75rem 1rem",
                background: "rgba(239,68,68,0.1)",
                border: "1px solid rgba(239,68,68,0.3)",
                borderRadius: "var(--radius-sm)",
                color: "var(--danger)",
                fontSize: "0.875rem",
              }}>
                ❌ {uploadError}
              </div>
            )}
          </div>
        )}

        {/* ── UPLOADING ── */}
        {appState === "uploading" && (
          <div style={{ maxWidth: "480px", margin: "4rem auto", textAlign: "center" }}>
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>⬆️</div>
            <p style={{ fontWeight: 600, marginBottom: "1rem" }}>
              Uploading {currentFile?.name}…
            </p>
            <div className="progress-track">
              <div className="progress-bar" style={{ width: `${uploadProgress}%` }} />
            </div>
            <p className="text-muted" style={{ fontSize: "0.8rem", marginTop: "0.5rem" }}>
              {uploadProgress}%
            </p>
          </div>
        )}

        {/* ── PROCESSING ── */}
        {appState === "processing" && (
          <div style={{ maxWidth: "480px", margin: "4rem auto", textAlign: "center" }}>
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>🔍</div>
            <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>
              Analysing drawing with AI…
            </p>
            <p className="text-muted" style={{ fontSize: "0.85rem", marginBottom: "1.5rem" }}>
              Extracting pipe runs, fittings, flanges, valves and dimensions
            </p>
            <div className="progress-track">
              <div className="progress-bar-indeterminate" />
            </div>
            <p className="text-muted" style={{ fontSize: "0.75rem", marginTop: "1rem" }}>
              Job ID: {jobId}
            </p>
          </div>
        )}

        {/* ── RESULTS ── */}
        {appState === "results" && result && (
          <ResultsPanel result={result} previewUrl={previewUrl} filename={currentFile?.name} jobId={jobId!} />
        )}
      </div>
    </main>
  );
}

// ── Results Panel (Sprint 0 skeleton — full components in Sprint 7&8) ───────

function ResultsPanel({
  result,
  previewUrl,
  filename,
  jobId,
}: {
  result: MTOResult;
  previewUrl: string | null;
  filename?: string;
  jobId: string;
}) {
  const [hoveredItem, setHoveredItem] = useState<number | null>(null);
  const [sortCol, setSortCol] = useState<string>("item_no");
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = [...result.items].sort((a, b) => {
    const av = (a as Record<string, unknown>)[sortCol];
    const bv = (b as Record<string, unknown>)[sortCol];
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return sortAsc ? -1 : 1;
    if (av > bv) return sortAsc ? 1 : -1;
    return 0;
  });

  const handleSort = (col: string) => {
    if (col === sortCol) setSortAsc((p) => !p);
    else { setSortCol(col); setSortAsc(true); }
  };

  const confClass = (c: number) => c >= 0.85 ? "conf-row-high" : c >= 0.6 ? "conf-row-mid" : "conf-row-low";
  const confColor = (c: number) => c >= 0.85 ? "var(--conf-high)" : c >= 0.6 ? "var(--conf-mid)" : "var(--conf-low)";

  const catColor: Record<string, string> = {
    PIPE: "#60a5fa", FITTING: "#34d399", FLANGE: "#fbbf24",
    VALVE: "#f87171", GASKET: "#c4b5fd", BOLT: "#9ca3af", SUPPORT: "#5eead4",
  };

  const downloadFile = (url: string, name: string) => {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
  };

  const { drawing_meta: m, summary: s } = result;

  return (
    <div>
      {/* Summary Cards */}
      <div className="summary-grid" style={{ marginBottom: "1.5rem" }}>
        {[
          { label: "Pipe Length", value: `${s.total_pipe_length_m.toFixed(2)}m` },
          { label: "Fittings", value: s.fittings },
          { label: "Flanges", value: s.flanges },
          { label: "Valves", value: s.valves },
          { label: "Gaskets", value: s.gaskets },
          { label: "Bolt Sets", value: s.bolt_sets },
          { label: "Field Welds", value: s.field_welds },
          { label: "Low Conf.", value: s.low_confidence_items, warn: s.low_confidence_items > 0 },
        ].map(({ label, value, warn }) => (
          <div key={label} className="summary-card">
            <div className="value" style={warn ? { color: "var(--warning)" } : {}}>
              {value}
            </div>
            <div className="label">{label}</div>
          </div>
        ))}
      </div>

      {/* Main layout: drawing + table */}
      <div style={{ display: "grid", gridTemplateColumns: previewUrl ? "1fr 1.8fr" : "1fr", gap: "1.5rem" }}>

        {/* Drawing Preview */}
        {previewUrl && (
          <div className="card" style={{ padding: "1rem" }}>
            <h3 style={{ marginBottom: "0.75rem", color: "var(--text-secondary)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Drawing Preview
            </h3>
            <div className="drawing-container">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previewUrl} alt="Isometric drawing" />
              {/* SVG overlay — full implementation in Sprint 8 */}
              <svg
                className="bbox-overlay interactive"
                viewBox="0 0 1 1"
                preserveAspectRatio="none"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
              >
                {result.items.filter(i => i.bbox).map(item => {
                  const b = item.bbox!;
                  const isHovered = hoveredItem === item.item_no;
                  const color = catColor[item.category] || "#fff";
                  return (
                      <rect
                        key={item.item_no}
                        x={b.x} y={b.y} width={b.width} height={b.height}
                        fill={isHovered ? `${color}33` : "transparent"}
                        stroke={color}
                        strokeWidth={isHovered ? 0.008 : 0.003}
                        rx={0.004}
                        style={{ cursor: "pointer", transition: "all 0.15s" }}
                        onMouseEnter={() => {
                          setHoveredItem(item.item_no);
                          const row = document.getElementById(`mto-row-${item.item_no}`);
                          if (row) {
                            row.scrollIntoView({ behavior: "smooth", block: "nearest" });
                          }
                        }}
                        onMouseLeave={() => setHoveredItem(null)}
                      />
                  );
                })}
              </svg>
            </div>

            {/* Meta panel */}
            <div style={{ marginTop: "1rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.78rem" }}>
              {[
                ["Drawing No.", m.drawing_no],
                ["Revision", m.revision],
                ["Line No.", m.line_number],
                ["NPS", m.nps],
                ["Material Class", m.material_class],
                ["Service", m.service],
                ["Design Press.", m.design_pressure],
                ["Design Temp.", m.design_temperature],
              ].filter(([, v]) => v).map(([label, value]) => (
                <div key={label as string}>
                  <span style={{ color: "var(--text-muted)" }}>{label}: </span>
                  <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{value}</span>
                </div>
              ))}
            </div>

            {m.line_number_parsed && (
              <div style={{ marginTop: "0.75rem", padding: "0.5rem", background: "var(--bg-secondary)", borderRadius: "var(--radius-sm)" }}>
                <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  Line Number Decoded
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", fontSize: "0.75rem" }}>
                  {Object.entries(m.line_number_parsed)
                    .filter(([k, v]) => k !== "raw" && v)
                    .map(([k, v]) => (
                      <span key={k} style={{ background: "var(--bg-card)", padding: "0.1rem 0.5rem", borderRadius: "4px", border: "1px solid var(--border)" }}>
                        <span style={{ color: "var(--text-muted)" }}>{k}: </span>
                        <span style={{ color: "var(--accent-light)" }}>{v}</span>
                      </span>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* MTO Table */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {/* Table header actions */}
          <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.75rem" }}>
            <div>
              <h3>Material Take-Off</h3>
              <p className="text-muted" style={{ fontSize: "0.75rem", marginTop: "0.15rem" }}>
                {result.items.length} items · {result.source === "mock" ? "Mock data" : `AI extracted in ${result.processing_time_s}s`}
              </p>
            </div>
            <div className="flex gap-sm flex-wrap">
              <button
                id="btn-download-csv"
                className="btn btn-secondary"
                style={{ fontSize: "0.8rem" }}
                onClick={() => downloadFile(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/mto/${jobId}/csv`, `mto_${jobId.slice(0,8)}.csv`)}
              >
                ⬇ CSV
              </button>
              <button
                id="btn-download-xlsx"
                className="btn btn-success"
                style={{ fontSize: "0.8rem" }}
                onClick={() => downloadFile(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/mto/${jobId}/xlsx`, `mto_${jobId.slice(0,8)}.xlsx`)}
              >
                ⬇ Excel
              </button>
            </div>
          </div>

          {/* Table */}
          <div style={{ overflowX: "auto", maxHeight: "calc(100vh - 320px)", overflowY: "auto" }}>
            <table className="mto-table">
              <thead>
                <tr>
                  {[
                    ["#", "item_no"],
                    ["Category", "category"],
                    ["Description", "description"],
                    ["Size", "size_nps"],
                    ["Sched./Rating", "schedule_rating"],
                    ["Material", "material_spec"],
                    ["End", "end_type"],
                    ["Qty", "quantity"],
                    ["Unit", "unit"],
                    ["Length (m)", "length_m"],
                    ["Conf.", "confidence"],
                    ["Remarks", "remarks"],
                  ].map(([label, col]) => (
                    <th key={col} onClick={() => handleSort(col)}>
                      {label} {sortCol === col ? (sortAsc ? "↑" : "↓") : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((item) => (
                  <tr
                    key={item.item_no}
                    id={`mto-row-${item.item_no}`}
                    className={`${confClass(item.confidence)} ${hoveredItem === item.item_no ? "highlighted" : ""}`}
                    onMouseEnter={() => setHoveredItem(item.item_no)}
                    onMouseLeave={() => setHoveredItem(null)}
                  >
                    <td>{item.item_no}</td>
                    <td>
                      <span style={{
                        background: `${catColor[item.category]}22`,
                        color: catColor[item.category] || "var(--text-secondary)",
                        padding: "0.15rem 0.5rem",
                        borderRadius: "4px",
                        fontSize: "0.72rem",
                        fontWeight: 600,
                      }}>
                        {item.category}
                      </span>
                    </td>
                    <td style={{ minWidth: "200px", color: "var(--text-primary)" }}>{item.description}</td>
                    <td>{item.size_nps}</td>
                    <td>{item.schedule_rating || "—"}</td>
                    <td style={{ minWidth: "140px" }}>{item.material_spec || "—"}</td>
                    <td>{item.end_type || "—"}</td>
                    <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{item.quantity}</td>
                    <td>{item.unit}</td>
                    <td>{item.length_m != null ? item.length_m.toFixed(2) : "—"}</td>
                    <td>
                      <span style={{ color: confColor(item.confidence), fontWeight: 600, fontSize: "0.8rem" }}>
                        {(item.confidence * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td style={{ maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.remarks || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper in the component (avoid sessionStorage issue by passing jobId)
function downloadFile(url: string, name: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
