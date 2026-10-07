import type { Config } from "tailwindcss";

/**
 * Colori del brand Huware: bianco, nero, ciano #00f5fe e turchese #00acc7.
 * Il ciano su bianco non ha contrasto sufficiente per il testo: si usa come evidenziatore
 * (testo nero su ciano, come nel sito) e come anello di focus. Per testo e link colorati
 * c'è `teal.700`, una tonalità scurita del turchese del brand (contrasto 4.5:1 su bianco).
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['"DM Sans Variable"', "DM Sans", "system-ui", "sans-serif"] },
      colors: {
        ink: "#0a0a0a",
        paper: "#ffffff",
        cyan: { DEFAULT: "#00f5fe", 100: "#e0fdff", 200: "#a8fbff", 300: "#6df8fe", 500: "#00f5fe" },
        teal: { DEFAULT: "#00acc7", 100: "#d6f3f8", 500: "#00acc7", 700: "#00798d" },
        surface: "#f4f6f7",
        line: "#e1e5e8",
        muted: "#5b6770",
      },
      letterSpacing: { tightest: "-0.035em" },
      boxShadow: { card: "0 1px 2px rgba(10,10,10,.05), 0 1px 1px rgba(10,10,10,.03)" },
    },
  },
  plugins: [],
} satisfies Config;
