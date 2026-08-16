import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Three roles, three faces — see app/layout.tsx.
        display: ["var(--font-display)", "ui-sans-serif", "system-ui", "sans-serif"],
        prose: ["var(--font-prose)", "ui-serif", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // `micro` replaces 56 hand-written text-[11px]; `mini` replaces text-[10px].
        mini: ["0.625rem", { lineHeight: "0.875rem" }],
        micro: ["0.6875rem", { lineHeight: "1rem" }],
      },
      colors: {
        // Ground
        paper: "hsl(var(--paper))",
        ink: "hsl(var(--ink))",
        graphite: "hsl(var(--graphite))",
        rule: "hsl(var(--rule))",

        // Data colour: direction, caution, and "you can click this".
        // Chrome stays ink/graphite so these stay legible as signal.
        bull: "hsl(var(--bull))",
        bear: "hsl(var(--bear))",
        halt: "hsl(var(--halt))",
        action: {
          DEFAULT: "hsl(var(--action))",
          foreground: "hsl(var(--action-foreground))",
        },

        // Semantic aliases for the shadcn primitives.
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
      },
      borderRadius: {
        // Every radius derives from --radius so the whole app moves together.
        sm: "calc(var(--radius) - 1px)",
        DEFAULT: "var(--radius)",
        md: "var(--radius)",
        lg: "calc(var(--radius) + 2px)",
        xl: "calc(var(--radius) + 4px)",
      },
      maxWidth: {
        shell: "1280px",
      },
      spacing: {
        topbar: "4rem",
      },
    },
  },
  plugins: [],
};

export default config;
