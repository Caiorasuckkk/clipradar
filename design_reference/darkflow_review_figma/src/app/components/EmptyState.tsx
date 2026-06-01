import { RefreshCw } from "lucide-react";

interface EmptyStateProps {
  onRefresh: () => void;
}

export function EmptyState({ onRefresh }: EmptyStateProps) {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 32px",
        gap: 20,
        textAlign: "center",
      }}
    >
      {/* Illustration */}
      <div
        style={{
          width: 96,
          height: 96,
          borderRadius: "50%",
          background: "var(--df-surface-3)",
          border: "1px solid rgba(255,255,255,0.07)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
          <rect x="6" y="14" width="40" height="28" rx="4" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" fill="none" />
          <path d="M22 26L28 22.5V29.5L22 26Z" fill="rgba(255,255,255,0.15)" />
          <path d="M6 20H46" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
          <circle cx="26" cy="44" r="3" fill="rgba(255,255,255,0.1)" />
          <rect x="16" y="42" width="20" height="2" rx="1" fill="rgba(255,255,255,0.08)" />
        </svg>
        <div
          style={{
            position: "absolute",
            top: -4,
            right: -4,
            width: 24,
            height: 24,
            borderRadius: "50%",
            background: "var(--df-surface-3)",
            border: "1px solid rgba(255,255,255,0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span style={{ fontSize: 13 }}>✓</span>
        </div>
      </div>

      <div>
        <h2
          style={{
            fontFamily: "'Inter',sans-serif",
            fontSize: 18,
            fontWeight: 700,
            color: "#e8eaf0",
            marginBottom: 8,
          }}
        >
          Nenhum clipe pendente
        </h2>
        <p
          style={{
            fontFamily: "'Inter',sans-serif",
            fontSize: 14,
            color: "#6b7280",
            lineHeight: 1.6,
            maxWidth: 260,
          }}
        >
          Renderize novos cortes no backend para continuar revisando.
        </p>
      </div>

      <button
        onClick={onRefresh}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "12px 28px",
          borderRadius: 12,
          background: "var(--df-neon-dim)",
          border: "1.5px solid var(--df-neon-border)",
          color: "var(--df-neon)",
          fontFamily: "'Inter',sans-serif",
          fontSize: 14,
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        <RefreshCw size={16} />
        Atualizar
      </button>
    </div>
  );
}
