import { Star } from "lucide-react";

interface RatingStarsProps {
  value: number;
  onChange: (v: number) => void;
}

export function RatingStars({ value, onChange }: RatingStarsProps) {
  return (
    <div
      style={{
        background: "var(--df-surface)",
        borderRadius: 14,
        border: "1px solid rgba(255,255,255,0.07)",
        padding: "14px 16px",
      }}
    >
      <p
        style={{
          fontFamily: "'JetBrains Mono',monospace",
          fontSize: 10,
          color: "#6b7280",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 12,
        }}
      >
        Avaliação
      </p>

      <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => onChange(star)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 4,
              transition: "transform 0.1s ease",
            }}
            onMouseDown={(e) => (e.currentTarget.style.transform = "scale(0.88)")}
            onMouseUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
            onTouchStart={(e) => (e.currentTarget.style.transform = "scale(0.88)")}
            onTouchEnd={(e) => (e.currentTarget.style.transform = "scale(1)")}
            aria-label={`${star} estrelas`}
          >
            <Star
              size={36}
              color={star <= value ? "#f59e0b" : "rgba(255,255,255,0.12)"}
              fill={star <= value ? "#f59e0b" : "transparent"}
              strokeWidth={star <= value ? 0 : 1.5}
              style={{
                filter: star <= value ? "drop-shadow(0 0 6px rgba(245,158,11,0.5))" : "none",
                transition: "all 0.15s ease",
              }}
            />
          </button>
        ))}
      </div>

      <div style={{ textAlign: "center", marginTop: 10 }}>
        {value > 0 ? (
          <span
            style={{
              fontFamily: "'JetBrains Mono',monospace",
              fontSize: 12,
              color: "#f59e0b",
              fontWeight: 500,
            }}
          >
            Nota: {value}/5
          </span>
        ) : (
          <span
            style={{
              fontFamily: "'JetBrains Mono',monospace",
              fontSize: 12,
              color: "#6b7280",
            }}
          >
            Toque para avaliar
          </span>
        )}
      </div>
    </div>
  );
}
