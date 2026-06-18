import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

/**
 * Favicon généré dynamiquement — remplace le "N" Next.js par défaut.
 * Affiché dans l'onglet du navigateur.
 */
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 15,
          background: "linear-gradient(135deg, #1d4ed8, #3b82f6)",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontWeight: 800,
          borderRadius: 7,
          letterSpacing: "-0.5px",
        }}
      >
        B
      </div>
    ),
    { ...size }
  );
}
