import { Clock, Tag, Tv, Zap } from "lucide-react";

interface ClipInfo {
  title: string;
  clipId: string;
  source: string;
  cutStart: string;
  cutEnd: string;
  analyzerScore?: number;
  analyzerReason?: string;
  sourceQuality?: string;
}

interface ClipInfoCardProps {
  clip: ClipInfo;
}

function InfoRow({ icon, label, value, accent }: { icon: React.ReactNode; label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
      <div style={{ marginTop: 1, color: accent ? "var(--df-neon)" : "#6b7280", flexShrink: 0 }}>{icon}</div>
      <div>
        <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {label}
        </span>
        <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 13, color: accent ? "var(--df-neon)" : "#c0c4d6", marginTop: 1, fontWeight: 500 }}>
          {value}
        </p>
      </div>
    </div>
  );
}

export function ClipInfoCard({ clip }: ClipInfoCardProps) {
  return (
    <div
      style={{
        background: "var(--df-surface)",
        borderRadius: 14,
        border: "1px solid rgba(255,255,255,0.07)",
        padding: 14,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      {/* Title */}
      <div>
        <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
          Título
        </p>
        <h2
          style={{
            fontFamily: "'Inter',sans-serif",
            fontSize: 14,
            fontWeight: 600,
            color: "#e8eaf0",
            lineHeight: 1.4,
          }}
        >
          {clip.title}
        </h2>
      </div>

      <div
        style={{
          height: 1,
          background: "rgba(255,255,255,0.06)",
          borderRadius: 1,
        }}
      />

      {/* Meta grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <InfoRow icon={<Tag size={13} />} label="ID" value={clip.clipId} />
        <InfoRow icon={<Tv size={13} />} label="Fonte" value={clip.source} />
        <InfoRow
          icon={<Clock size={13} />}
          label="Corte"
          value={`${clip.cutStart} → ${clip.cutEnd}`}
        />
        {clip.sourceQuality && (
          <InfoRow icon={<Zap size={13} />} label="Qualidade" value={clip.sourceQuality} />
        )}
      </div>

      {/* Analyzer data */}
      {(clip.analyzerScore !== undefined || clip.analyzerReason) && (
        <>
          <div style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />
          <div
            style={{
              background: "var(--df-neon-dim)",
              borderRadius: 10,
              border: "1px solid var(--df-neon-border)",
              padding: "10px 12px",
              display: "flex",
              gap: 12,
              alignItems: "flex-start",
            }}
          >
            {clip.analyzerScore !== undefined && (
              <div style={{ flexShrink: 0 }}>
                <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "var(--df-neon)", opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  IA score
                </p>
                <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 22, fontWeight: 700, color: "var(--df-neon)", lineHeight: 1.2 }}>
                  {clip.analyzerScore}
                </p>
              </div>
            )}
            {clip.analyzerReason && (
              <div>
                <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "var(--df-neon)", opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                  Motivo analyzer
                </p>
                <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 12, color: "#c0c4d6", lineHeight: 1.5 }}>
                  {clip.analyzerReason}
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
