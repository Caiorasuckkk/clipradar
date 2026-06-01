import { useState } from "react";
import { AppHeader } from "./components/AppHeader";
import { VideoReviewCard } from "./components/VideoReviewCard";
import { ClipInfoCard } from "./components/ClipInfoCard";
import { RatingStars } from "./components/RatingStars";
import { StatusButtons, type ReviewStatus } from "./components/StatusButtons";
import { ReasonChips } from "./components/ReasonChips";
import { NotesField } from "./components/NotesField";
import { EmptyState } from "./components/EmptyState";
import { SummarySheet } from "./components/SummarySheet";
import { DesignGuide } from "./components/DesignGuide";
import { SkipForward } from "lucide-react";

/* MARKER-MAKE-KIT-INVOKED */

type Screen = "review" | "filled" | "loading" | "error" | "empty" | "guide";

const MOCK_CLIP = {
  title: "Como a IA está mudando o mercado de trabalho em 2024 — análise completa",
  clipId: "clip_007",
  source: "Canal Tech BR",
  cutStart: "36:56",
  cutEnd: "37:50",
  analyzerScore: 8.4,
  analyzerReason: "Momento de alta intensidade com argumento central claro. Boa retenção esperada.",
  sourceQuality: "Alta (1080p/60fps)",
};

const SUMMARY_DATA = {
  total: 38,
  reviewed: 24,
  pending: 14,
  approved: 16,
  rejected: 5,
  adjusted: 3,
  avgRating: 3.8,
  topReasons: [
    { label: "ótimo", count: 11 },
    { label: "bom", count: 8 },
    { label: "sem contexto", count: 5 },
    { label: "precisa trim", count: 4 },
    { label: "não prendeu", count: 3 },
  ],
};

const SCREEN_LABELS: Record<Screen, string> = {
  review: "Revisão",
  filled: "Avaliação preenchida",
  loading: "Loading",
  error: "Erro no vídeo",
  empty: "Sem clipes",
  guide: "Design Guide",
};

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>("review");
  const [rating, setRating] = useState(0);
  const [status, setStatus] = useState<ReviewStatus>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [showSummary, setShowSummary] = useState(false);

  const isFilled = currentScreen === "filled";
  const filledRating = isFilled ? 4 : rating;
  const filledStatus: ReviewStatus = isFilled ? "approve" : status;
  const filledReasons = isFilled ? ["otimo", "perfeito"] : reasons;
  const filledNotes = isFilled ? "Excelente corte, começa direto no argumento. Ideal para shorts." : notes;

  const handleSave = () => {
    setRating(0);
    setStatus(null);
    setReasons([]);
    setNotes("");
  };

  const showVideoCard = currentScreen === "review" || currentScreen === "filled";
  const showLoadingCard = currentScreen === "loading";
  const showErrorCard = currentScreen === "error";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#04050a",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "20px 0 40px",
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* Mobile frame */}
      <div
        style={{
          width: "100%",
          maxWidth: 390,
          minHeight: "100vh",
          background: "var(--background)",
          position: "relative",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 0 80px rgba(0,0,0,0.8)",
        }}
      >
        {/* Screen picker — navigation bar */}
        <div
          style={{
            background: "#05060d",
            borderBottom: "1px solid rgba(255,255,255,0.05)",
            padding: "10px 12px",
            display: "flex",
            gap: 6,
            overflowX: "auto",
            flexShrink: 0,
          }}
        >
          {(Object.keys(SCREEN_LABELS) as Screen[]).map((s) => (
            <button
              key={s}
              onClick={() => {
                setCurrentScreen(s);
                setShowSummary(false);
              }}
              style={{
                padding: "6px 12px",
                borderRadius: 20,
                background: currentScreen === s ? "var(--df-neon-dim)" : "transparent",
                border: `1px solid ${currentScreen === s ? "var(--df-neon-border)" : "rgba(255,255,255,0.07)"}`,
                color: currentScreen === s ? "var(--df-neon)" : "#6b7280",
                fontFamily: "'JetBrains Mono',monospace",
                fontSize: 10,
                fontWeight: currentScreen === s ? 600 : 400,
                cursor: "pointer",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {SCREEN_LABELS[s]}
            </button>
          ))}
        </div>

        {/* DESIGN GUIDE screen */}
        {currentScreen === "guide" && <DesignGuide onClose={() => setCurrentScreen("review")} />}

        {/* EMPTY STATE screen */}
        {currentScreen === "empty" && (
          <>
            <AppHeader
              pending={0}
              reviewed={24}
              onRefresh={() => {}}
              onSummary={() => setShowSummary(true)}
            />
            <EmptyState onRefresh={() => setCurrentScreen("review")} />
          </>
        )}

        {/* MAIN REVIEW / FILLED / LOADING / ERROR screens */}
        {currentScreen !== "empty" && currentScreen !== "guide" && (
          <>
            <AppHeader
              pending={14}
              reviewed={24}
              onRefresh={() => {}}
              onSummary={() => setShowSummary(true)}
            />

            {/* Scrollable content */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "14px 14px 140px",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              {/* Clip counter */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#6b7280" }}>
                  Clipe 7 de 14
                </span>
                <div style={{ display: "flex", gap: 4 }}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div
                      key={i}
                      style={{
                        width: i < 3 ? 20 : 6,
                        height: 4,
                        borderRadius: 2,
                        background: i < 3 ? "var(--df-neon)" : "rgba(255,255,255,0.1)",
                        transition: "all 0.2s",
                      }}
                    />
                  ))}
                </div>
              </div>

              {/* Video card */}
              {showLoadingCard && (
                <VideoReviewCard forceState="loading" />
              )}
              {showErrorCard && (
                <VideoReviewCard forceState="error" />
              )}
              {showVideoCard && (
                <VideoReviewCard
                  forceState={isFilled ? "paused" : "paused"}
                  thumbnailUrl="https://images.unsplash.com/photo-1611532736597-de2d4265fba3?w=800&h=450&fit=crop&auto=format"
                />
              )}

              {/* Clip info */}
              <ClipInfoCard clip={MOCK_CLIP} />

              {/* Rating */}
              <RatingStars
                value={filledRating}
                onChange={isFilled ? () => {} : setRating}
              />

              {/* Status buttons */}
              <StatusButtons
                value={filledStatus}
                onChange={isFilled ? () => {} : setStatus}
              />

              {/* Reason chips */}
              <ReasonChips
                selected={filledReasons}
                onChange={isFilled ? () => {} : setReasons}
                status={filledStatus}
              />

              {/* Notes */}
              <NotesField
                value={filledNotes}
                onChange={isFilled ? () => {} : setNotes}
              />

              {/* Swipe hint */}
              <div
                style={{
                  background: "var(--df-surface)",
                  borderRadius: 10,
                  border: "1px solid rgba(255,255,255,0.05)",
                  padding: "10px 14px",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                <span style={{ fontSize: 16 }}>👆</span>
                <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 11, color: "#6b7280", lineHeight: 1.5 }}>
                  <span style={{ color: "var(--df-approve)" }}>→ aprovar</span>
                  {"  ·  "}
                  <span style={{ color: "var(--df-reject)" }}>← rejeitar</span>
                  {"  ·  "}
                  <span style={{ color: "var(--df-neon)" }}>↑ ótimo</span>
                  <span style={{ color: "#4b5563" }}> — gestos em breve</span>
                </p>
              </div>
            </div>

            {/* Fixed bottom action bar */}
            <div
              style={{
                position: "sticky",
                bottom: 0,
                left: 0,
                right: 0,
                background: "linear-gradient(0deg, #08090e 60%, rgba(8,9,14,0) 100%)",
                padding: "20px 14px 28px",
                display: "flex",
                flexDirection: "column",
                gap: 10,
                pointerEvents: "none",
              }}
            >
              {/* Save & Next */}
              <button
                onClick={handleSave}
                style={{
                  width: "100%",
                  height: 56,
                  borderRadius: 16,
                  background: "var(--df-neon)",
                  border: "none",
                  color: "#08090e",
                  fontFamily: "'Inter',sans-serif",
                  fontSize: 16,
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 4px 24px rgba(0,200,240,0.35)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                  pointerEvents: "all",
                  letterSpacing: "-0.01em",
                }}
              >
                Salvar e próximo
                <SkipForward size={18} />
              </button>

              {/* Skip */}
              <button
                style={{
                  width: "100%",
                  height: 44,
                  borderRadius: 12,
                  background: "transparent",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "#6b7280",
                  fontFamily: "'Inter',sans-serif",
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: "pointer",
                  pointerEvents: "all",
                }}
              >
                Pular
              </button>
            </div>
          </>
        )}

        {/* Summary bottom sheet */}
        {showSummary && (
          <SummarySheet data={SUMMARY_DATA} onClose={() => setShowSummary(false)} />
        )}
      </div>
    </div>
  );
}
