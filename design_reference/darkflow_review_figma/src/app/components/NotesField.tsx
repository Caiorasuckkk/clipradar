interface NotesFieldProps {
  value: string;
  onChange: (v: string) => void;
}

export function NotesField({ value, onChange }: NotesFieldProps) {
  return (
    <div
      style={{
        background: "var(--df-surface)",
        borderRadius: 14,
        border: "1px solid rgba(255,255,255,0.07)",
        padding: "12px 14px",
      }}
    >
      <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
        Observações
      </p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Observações opcionais sobre o corte..."
        rows={3}
        style={{
          width: "100%",
          background: "var(--df-surface-3)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 10,
          padding: "10px 12px",
          fontFamily: "'Inter',sans-serif",
          fontSize: 13,
          color: "#e8eaf0",
          resize: "none",
          outline: "none",
          boxSizing: "border-box",
          lineHeight: 1.5,
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = "var(--df-neon-border)";
          e.currentTarget.style.boxShadow = "0 0 0 2px var(--df-neon-dim)";
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)";
          e.currentTarget.style.boxShadow = "none";
        }}
      />
    </div>
  );
}
