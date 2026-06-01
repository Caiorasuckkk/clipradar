import type { ReviewStatus } from "./StatusButtons";

const REASONS: Record<string, { label: string; type: "positive" | "adjust" | "negative" }> = {
  bom: { label: "bom", type: "positive" },
  otimo: { label: "ótimo", type: "positive" },
  perfeito: { label: "perfeito", type: "positive" },
  bom_curto: { label: "bom mas curto", type: "adjust" },
  bom_longo: { label: "bom mas longo", type: "adjust" },
  final_encurtar: { label: "final poderia encurtar", type: "adjust" },
  emendou: { label: "emendou assuntos", type: "adjust" },
  precisa_trim: { label: "precisa trim", type: "adjust" },
  ruim: { label: "ruim", type: "negative" },
  sem_contexto: { label: "sem contexto", type: "negative" },
  nao_prendeu: { label: "não prendeu", type: "negative" },
  propaganda: { label: "propaganda", type: "negative" },
  topic_merge: { label: "topic merge", type: "negative" },
  video_fraco: { label: "vídeo fraco", type: "negative" },
};

interface ReasonChipsProps {
  selected: string[];
  onChange: (reasons: string[]) => void;
  status: ReviewStatus;
}

function getChipColors(type: string, isActive: boolean) {
  if (type === "positive") return {
    bg: isActive ? "rgba(16,185,129,0.18)" : "var(--df-surface-3)",
    border: isActive ? "rgba(16,185,129,0.4)" : "rgba(255,255,255,0.07)",
    text: isActive ? "var(--df-approve)" : "#9ca3af",
  };
  if (type === "adjust") return {
    bg: isActive ? "rgba(245,158,11,0.18)" : "var(--df-surface-3)",
    border: isActive ? "rgba(245,158,11,0.4)" : "rgba(255,255,255,0.07)",
    text: isActive ? "var(--df-adjust)" : "#9ca3af",
  };
  return {
    bg: isActive ? "rgba(239,68,68,0.18)" : "var(--df-surface-3)",
    border: isActive ? "rgba(239,68,68,0.4)" : "rgba(255,255,255,0.07)",
    text: isActive ? "var(--df-reject)" : "#9ca3af",
  };
}

function ChipGroup({ title, keys, selected, onChange }: { title: string; keys: string[]; selected: string[]; onChange: (r: string[]) => void }) {
  return (
    <div>
      <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
        {title}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {keys.map((key) => {
          const reason = REASONS[key];
          const isActive = selected.includes(key);
          const colors = getChipColors(reason.type, isActive);
          return (
            <button
              key={key}
              onClick={() => {
                onChange(isActive ? selected.filter((r) => r !== key) : [...selected, key]);
              }}
              style={{
                padding: "6px 12px",
                borderRadius: 20,
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                color: colors.text,
                fontFamily: "'Inter',sans-serif",
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                cursor: "pointer",
                transition: "all 0.12s ease",
                whiteSpace: "nowrap",
              }}
            >
              {reason.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ReasonChips({ selected, onChange }: ReasonChipsProps) {
  return (
    <div
      style={{
        background: "var(--df-surface)",
        borderRadius: 14,
        border: "1px solid rgba(255,255,255,0.07)",
        padding: "14px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Motivos rápidos
      </p>
      <ChipGroup title="Positivos" keys={["bom", "otimo", "perfeito"]} selected={selected} onChange={onChange} />
      <ChipGroup title="Ajustes" keys={["bom_curto", "bom_longo", "final_encurtar", "emendou", "precisa_trim"]} selected={selected} onChange={onChange} />
      <ChipGroup title="Negativos" keys={["ruim", "sem_contexto", "nao_prendeu", "propaganda", "topic_merge", "video_fraco"]} selected={selected} onChange={onChange} />
    </div>
  );
}
