import { X, TrendingUp, CheckCircle2, XCircle, Settings2, Clock, Star } from "lucide-react";

interface SummaryData {
  total: number;
  reviewed: number;
  pending: number;
  approved: number;
  rejected: number;
  adjusted: number;
  avgRating: number;
  topReasons: Array<{ label: string; count: number }>;
}

interface SummarySheetProps {
  data: SummaryData;
  onClose: () => void;
}

function StatCard({ label, value, color, icon }: { label: string; value: number | string; color: string; icon: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--df-surface-2)",
        borderRadius: 12,
        border: "1px solid rgba(255,255,255,0.07)",
        padding: "12px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ color, opacity: 0.7 }}>{icon}</div>
      <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>
        {value}
      </p>
      <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 11, color: "#6b7280", marginTop: 2 }}>
        {label}
      </p>
    </div>
  );
}

export function SummarySheet({ data, onClose }: SummarySheetProps) {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          background: "rgba(0,0,0,0.7)",
          backdropFilter: "blur(4px)",
        }}
      />

      {/* Sheet */}
      <div
        style={{
          position: "relative",
          background: "var(--df-surface)",
          borderRadius: "20px 20px 0 0",
          border: "1px solid rgba(255,255,255,0.08)",
          borderBottom: "none",
          padding: "0 0 32px",
          maxHeight: "85vh",
          overflowY: "auto",
        }}
      >
        {/* Handle */}
        <div style={{ display: "flex", justifyContent: "center", padding: "12px 0 4px" }}>
          <div style={{ width: 36, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.15)" }} />
        </div>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 20px 20px" }}>
          <div>
            <h2 style={{ fontFamily: "'Inter',sans-serif", fontSize: 17, fontWeight: 700, color: "#e8eaf0" }}>
              Resumo
            </h2>
            <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#6b7280", marginTop: 2 }}>
              {data.total} clipes no total
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 36, height: 36, borderRadius: 10,
              background: "var(--df-surface-3)",
              border: "1px solid rgba(255,255,255,0.06)",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <X size={16} color="#6b7280" />
          </button>
        </div>

        {/* Stats grid */}
        <div style={{ padding: "0 16px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
          <StatCard label="Revisados" value={data.reviewed} color="var(--df-neon)" icon={<TrendingUp size={15} />} />
          <StatCard label="Aprovados" value={data.approved} color="var(--df-approve)" icon={<CheckCircle2 size={15} />} />
          <StatCard label="Rejeitados" value={data.rejected} color="var(--df-reject)" icon={<XCircle size={15} />} />
          <StatCard label="Ajustes" value={data.adjusted} color="var(--df-adjust)" icon={<Settings2 size={15} />} />
          <StatCard label="Pendentes" value={data.pending} color="#6b7280" icon={<Clock size={15} />} />
          <StatCard label="Nota média" value={`${data.avgRating.toFixed(1)}/5`} color="#f59e0b" icon={<Star size={15} />} />
        </div>

        {/* Progress bar */}
        <div style={{ padding: "20px 16px 0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Progresso
            </span>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "var(--df-neon)" }}>
              {Math.round((data.reviewed / data.total) * 100)}%
            </span>
          </div>
          <div style={{ height: 6, background: "var(--df-surface-3)", borderRadius: 3, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${(data.reviewed / data.total) * 100}%`,
                background: "linear-gradient(90deg, var(--df-neon), #0099bb)",
                borderRadius: 3,
                boxShadow: "0 0 10px rgba(0,200,240,0.4)",
              }}
            />
          </div>
        </div>

        {/* Top reasons */}
        {data.topReasons.length > 0 && (
          <div style={{ padding: "20px 16px 0" }}>
            <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
              Motivos mais usados
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {data.topReasons.map((r, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 13, color: "#c0c4d6", flex: 1 }}>
                    {r.label}
                  </span>
                  <div style={{ flex: 2, height: 4, background: "var(--df-surface-3)", borderRadius: 2, overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${(r.count / data.topReasons[0].count) * 100}%`,
                        background: "var(--df-neon)",
                        borderRadius: 2,
                        opacity: 0.7,
                      }}
                    />
                  </div>
                  <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#6b7280", minWidth: 20, textAlign: "right" }}>
                    {r.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
