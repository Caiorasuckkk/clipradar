import { RefreshCw, BarChart2 } from "lucide-react";

interface AppHeaderProps {
  pending: number;
  reviewed: number;
  onRefresh: () => void;
  onSummary: () => void;
}

export function AppHeader({ pending, reviewed, onRefresh, onSummary }: AppHeaderProps) {
  return (
    <header
      style={{
        background: "linear-gradient(180deg, #0f1018 0%, rgba(15,16,24,0.95) 100%)",
        borderBottom: "1px solid var(--df-neon-border)",
      }}
      className="flex items-center justify-between px-4 py-3 sticky top-0 z-50"
    >
      <div className="flex items-center gap-2">
        <div
          style={{
            width: 28,
            height: 28,
            background: "var(--df-neon-dim)",
            border: "1px solid var(--df-neon-border)",
            borderRadius: 6,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 4L8 2L13 4V8C13 11 8 14 8 14C8 14 3 11 3 8V4Z" fill="var(--df-neon)" opacity="0.3"/>
            <path d="M6 8L7.5 9.5L10 7" stroke="var(--df-neon)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <span
          style={{
            fontFamily: "'Inter', sans-serif",
            fontWeight: 700,
            fontSize: 15,
            letterSpacing: "-0.02em",
            color: "var(--df-neon)",
          }}
        >
          DarkFlow
          <span style={{ color: "#e8eaf0", fontWeight: 500 }}> Review</span>
        </span>
      </div>

      <div className="flex items-center gap-2">
        <div
          style={{
            background: "var(--df-surface-3)",
            borderRadius: 20,
            padding: "4px 10px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "var(--df-neon)", fontWeight: 500 }}>
            {pending} pend.
          </span>
          <div style={{ width: 1, height: 12, background: "rgba(255,255,255,0.1)" }} />
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#6b7280", fontWeight: 400 }}>
            {reviewed} rev.
          </span>
        </div>

        <button
          onClick={onSummary}
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            background: "var(--df-surface-3)",
            border: "1px solid rgba(255,255,255,0.06)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
          aria-label="Resumo"
        >
          <BarChart2 size={16} color="#6b7280" />
        </button>

        <button
          onClick={onRefresh}
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            background: "var(--df-surface-3)",
            border: "1px solid rgba(255,255,255,0.06)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
          aria-label="Atualizar"
        >
          <RefreshCw size={16} color="#6b7280" />
        </button>
      </div>
    </header>
  );
}
