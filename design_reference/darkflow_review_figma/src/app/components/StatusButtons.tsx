import { ThumbsDown, Settings2, ThumbsUp } from "lucide-react";

export type ReviewStatus = "reject" | "adjust" | "approve" | null;

interface StatusButtonsProps {
  value: ReviewStatus;
  onChange: (v: ReviewStatus) => void;
}

const BUTTONS = [
  {
    id: "reject" as ReviewStatus,
    label: "Rejeitar",
    icon: ThumbsDown,
    color: "var(--df-reject)",
    dimColor: "var(--df-reject-dim)",
    borderColor: "rgba(239,68,68,0.3)",
  },
  {
    id: "adjust" as ReviewStatus,
    label: "Ajustar",
    icon: Settings2,
    color: "var(--df-adjust)",
    dimColor: "var(--df-adjust-dim)",
    borderColor: "rgba(245,158,11,0.3)",
  },
  {
    id: "approve" as ReviewStatus,
    label: "Aprovar",
    icon: ThumbsUp,
    color: "var(--df-approve)",
    dimColor: "var(--df-approve-dim)",
    borderColor: "rgba(16,185,129,0.3)",
  },
];

export function StatusButtons({ value, onChange }: StatusButtonsProps) {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      {BUTTONS.map((btn) => {
        const Icon = btn.icon;
        const isActive = value === btn.id;
        return (
          <button
            key={btn.id}
            onClick={() => onChange(isActive ? null : btn.id)}
            style={{
              flex: 1,
              height: 56,
              borderRadius: 14,
              background: isActive ? btn.dimColor : "var(--df-surface)",
              border: `1.5px solid ${isActive ? btn.borderColor : "rgba(255,255,255,0.07)"}`,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 5,
              cursor: "pointer",
              transition: "all 0.15s ease",
              boxShadow: isActive ? `0 0 16px ${btn.dimColor}` : "none",
            }}
          >
            <Icon
              size={18}
              color={isActive ? btn.color : "#6b7280"}
              style={{ transition: "color 0.15s" }}
            />
            <span
              style={{
                fontFamily: "'Inter',sans-serif",
                fontSize: 11,
                fontWeight: isActive ? 700 : 500,
                color: isActive ? btn.color : "#6b7280",
                transition: "color 0.15s",
              }}
            >
              {btn.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
