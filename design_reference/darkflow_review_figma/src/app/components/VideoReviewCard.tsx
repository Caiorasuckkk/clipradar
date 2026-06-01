import { useState, useRef } from "react";
import { Play, Pause, RotateCcw, AlertCircle, Loader2, Volume2 } from "lucide-react";

type VideoState = "loading" | "playing" | "paused" | "error";

interface VideoReviewCardProps {
  forceState?: VideoState;
  thumbnailUrl?: string;
}

export function VideoReviewCard({ forceState, thumbnailUrl }: VideoReviewCardProps) {
  const [videoState, setVideoState] = useState<VideoState>(forceState ?? "paused");
  const [progress, setProgress] = useState(0.35);
  const [isDragging, setIsDragging] = useState(false);
  const progressRef = useRef<HTMLDivElement>(null);

  const currentTime = "1:12";
  const duration = "0:54";

  const togglePlay = () => {
    if (videoState === "error" || videoState === "loading") return;
    setVideoState((s) => (s === "playing" ? "paused" : "playing"));
  };

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = progressRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    setProgress(Math.max(0, Math.min(1, x / rect.width)));
  };

  const state = forceState ?? videoState;

  return (
    <div
      style={{
        background: "#000",
        borderRadius: 16,
        overflow: "hidden",
        position: "relative",
        aspectRatio: "16/9",
        border: "1px solid rgba(255,255,255,0.08)",
        boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
      }}
    >
      {/* Thumbnail/Video background */}
      {thumbnailUrl && state !== "error" && (
        <img
          src={thumbnailUrl}
          alt="Video thumbnail"
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: 0.7 }}
        />
      )}

      {/* Gradient overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            state === "playing"
              ? "linear-gradient(to bottom, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.7) 100%)"
              : "linear-gradient(to bottom, rgba(0,0,0,0.2) 0%, rgba(0,0,0,0.1) 40%, rgba(0,0,0,0.8) 100%)",
        }}
      />

      {/* LOADING STATE */}
      {state === "loading" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            background: "rgba(8,9,14,0.9)",
          }}
        >
          <Loader2 size={36} color="var(--df-neon)" className="animate-spin" />
          <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: "#6b7280" }}>
            Carregando clipe...
          </span>
        </div>
      )}

      {/* ERROR STATE */}
      {state === "error" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            background: "rgba(8,9,14,0.95)",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              background: "var(--df-reject-dim)",
              border: "1px solid rgba(239,68,68,0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <AlertCircle size={24} color="var(--df-reject)" />
          </div>
          <div style={{ textAlign: "center" }}>
            <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 14, fontWeight: 600, color: "#e8eaf0", marginBottom: 4 }}>
              Erro ao carregar vídeo
            </p>
            <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 12, color: "#6b7280" }}>
              Verifique a URL ou tente novamente
            </p>
          </div>
          <button
            style={{
              padding: "8px 20px",
              borderRadius: 8,
              background: "var(--df-reject-dim)",
              border: "1px solid rgba(239,68,68,0.3)",
              color: "var(--df-reject)",
              fontFamily: "'Inter',sans-serif",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* CENTER PLAY/PAUSE BUTTON */}
      {(state === "playing" || state === "paused") && (
        <button
          onClick={togglePlay}
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%,-50%)",
            width: 56,
            height: 56,
            borderRadius: "50%",
            background: state === "playing" ? "rgba(0,0,0,0.4)" : "rgba(0,200,240,0.15)",
            border: state === "playing" ? "1px solid rgba(255,255,255,0.2)" : "2px solid var(--df-neon)",
            backdropFilter: "blur(8px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: "all 0.15s ease",
            opacity: state === "playing" ? 0 : 1,
          }}
          className="group-hover:opacity-100"
          aria-label={state === "playing" ? "Pausar" : "Play"}
        >
          {state === "playing" ? (
            <Pause size={22} color="#fff" fill="#fff" />
          ) : (
            <Play size={22} color="var(--df-neon)" fill="var(--df-neon)" style={{ marginLeft: 2 }} />
          )}
        </button>
      )}

      {/* BOTTOM CONTROLS */}
      {(state === "playing" || state === "paused") && (
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            padding: "8px 12px 10px",
          }}
        >
          {/* Progress bar */}
          <div
            ref={progressRef}
            onClick={handleProgressClick}
            style={{
              height: 3,
              background: "rgba(255,255,255,0.2)",
              borderRadius: 2,
              marginBottom: 8,
              cursor: "pointer",
              position: "relative",
            }}
          >
            <div
              style={{
                width: `${progress * 100}%`,
                height: "100%",
                background: "var(--df-neon)",
                borderRadius: 2,
                boxShadow: "0 0 8px var(--df-neon)",
                transition: isDragging ? "none" : "width 0.1s",
              }}
            />
            <div
              style={{
                position: "absolute",
                top: "50%",
                left: `${progress * 100}%`,
                transform: "translate(-50%, -50%)",
                width: 12,
                height: 12,
                borderRadius: "50%",
                background: "var(--df-neon)",
                boxShadow: "0 0 8px var(--df-neon)",
              }}
            />
          </div>

          {/* Time + controls row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button onClick={togglePlay} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                {state === "playing" ? (
                  <Pause size={18} color="#e8eaf0" fill="#e8eaf0" />
                ) : (
                  <Play size={18} color="#e8eaf0" fill="#e8eaf0" style={{ marginLeft: 1 }} />
                )}
              </button>
              <button
                onClick={() => setProgress(0)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
              >
                <RotateCcw size={15} color="#9ca3af" />
              </button>
              <span
                style={{
                  fontFamily: "'JetBrains Mono',monospace",
                  fontSize: 11,
                  color: "#9ca3af",
                }}
              >
                {currentTime} / {duration}
              </span>
            </div>
            <Volume2 size={15} color="#9ca3af" />
          </div>
        </div>
      )}

      {/* Swipe hint overlay — visual indicator only */}
      <div
        style={{
          position: "absolute",
          top: 10,
          right: 10,
          display: "flex",
          flexDirection: "column",
          gap: 4,
          opacity: 0.5,
        }}
      >
        <div
          style={{
            fontSize: 9,
            fontFamily: "'JetBrains Mono',monospace",
            color: "#6b7280",
            textAlign: "right",
            lineHeight: 1.4,
          }}
        >
          ← rejeitar &nbsp; aprovar →
        </div>
      </div>
    </div>
  );
}
