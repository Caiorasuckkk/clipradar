import { X } from "lucide-react";

interface DesignGuideProps {
  onClose: () => void;
}

const COLORS = [
  { name: "Background", value: "#08090e", label: "--background" },
  { name: "Surface", value: "#0f1018", label: "--df-surface" },
  { name: "Surface 2", value: "#13141f", label: "--df-surface-2" },
  { name: "Surface 3", value: "#1a1c28", label: "--df-surface-3" },
  { name: "Neon Cyan", value: "#00c8f0", label: "--df-neon (primary)" },
  { name: "Approve", value: "#10b981", label: "--df-approve" },
  { name: "Adjust", value: "#f59e0b", label: "--df-adjust" },
  { name: "Reject", value: "#ef4444", label: "--df-reject" },
  { name: "Foreground", value: "#e8eaf0", label: "--foreground" },
  { name: "Muted", value: "#6b7280", label: "--muted-foreground" },
  { name: "Border", value: "rgba(255,255,255,0.08)", label: "--border" },
];

const SPACING = [4, 8, 10, 12, 14, 16, 20, 24, 32, 40];

export function DesignGuide({ onClose }: DesignGuideProps) {
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 200, overflowY: "auto", background: "var(--df-surface)" }}>
      <div style={{ padding: "16px 16px 40px", maxWidth: 420, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <h1 style={{ fontFamily: "'Inter',sans-serif", fontSize: 20, fontWeight: 700, color: "var(--df-neon)" }}>
              Design Guide
            </h1>
            <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#6b7280" }}>
              DarkFlow Review — v1.0
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ width: 36, height: 36, borderRadius: 10, background: "var(--df-surface-3)", border: "1px solid rgba(255,255,255,0.07)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}
          >
            <X size={16} color="#6b7280" />
          </button>
        </div>

        {/* Colors */}
        <Section title="Cores">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {COLORS.map((c) => (
              <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: c.value, border: "1px solid rgba(255,255,255,0.1)", flexShrink: 0 }} />
                <div>
                  <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 13, color: "#e8eaf0", fontWeight: 500 }}>{c.name}</p>
                  <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#6b7280" }}>{c.value} · {c.label}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Typography */}
        <Section title="Tipografia">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <TypoRow label="Display / Title" font="Inter" weight={700} size={20} sample="DarkFlow Review" />
            <TypoRow label="Heading" font="Inter" weight={600} size={16} sample="Revisar Clipes" />
            <TypoRow label="Body" font="Inter" weight={400} size={14} sample="Observações opcionais sobre o corte..." />
            <TypoRow label="Label / UI" font="Inter" weight={500} size={12} sample="Aprovar · Rejeitar · Ajustar" />
            <TypoRow label="Mono data" font="JetBrains Mono" weight={400} size={12} sample="clip_id_007 · 36:56 → 37:50" mono />
            <TypoRow label="Mono display" font="JetBrains Mono" weight={700} size={22} sample="4.2/5" mono />
          </div>
        </Section>

        {/* Spacing */}
        <Section title="Espaçamento (px)">
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {SPACING.map((s) => (
              <div key={s} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                <div style={{ width: s, height: s, background: "var(--df-neon)", opacity: 0.3, borderRadius: 2 }} />
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: "#6b7280" }}>{s}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Radii */}
        <Section title="Border Radius">
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {[6, 8, 10, 12, 14, 16, 20].map((r) => (
              <div key={r} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <div style={{ width: 40, height: 40, background: "var(--df-surface-3)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: r }} />
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: "#6b7280" }}>{r}px</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Flutter notes */}
        <Section title="Flutter Notes">
          <div style={{ background: "var(--df-surface-3)", borderRadius: 10, padding: 14, border: "1px solid rgba(255,255,255,0.06)" }}>
            <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#9ca3af", lineHeight: 1.6 }}>
              • Fundo: Color(0xFF08090E){"\n"}
              • Neon Cyan: Color(0xFF00C8F0){"\n"}
              • Surface cards: Color(0xFF0F1018){"\n"}
              • Fonte primária: Inter (Google Fonts){"\n"}
              • Fonte mono: JetBrains Mono{"\n"}
              • Border radius padrão: 14.0{"\n"}
              • Swipe: GestureDetector com HorizontalDragEnd{"\n"}
              • Bottom sheet: DraggableScrollableSheet
            </p>
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <div style={{ width: 3, height: 16, background: "var(--df-neon)", borderRadius: 2 }} />
        <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "var(--df-neon)", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600 }}>
          {title}
        </p>
      </div>
      {children}
    </div>
  );
}

function TypoRow({ label, font, weight, size, sample, mono }: { label: string; font: string; weight: number; size: number; sample: string; mono?: boolean }) {
  return (
    <div style={{ padding: "10px 12px", background: "var(--df-surface-3)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.06)" }}>
      <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: "#6b7280", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        {label} · {font} {weight} · {size}px
      </p>
      <p
        style={{
          fontFamily: mono ? "'JetBrains Mono',monospace" : "'Inter',sans-serif",
          fontWeight: weight,
          fontSize: size,
          color: "#e8eaf0",
          lineHeight: 1.3,
        }}
      >
        {sample}
      </p>
    </div>
  );
}
