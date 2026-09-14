/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{html,ts}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Glass system tokens
        glass: {
          bg: "rgba(255,255,255,0.60)",
          border: "rgba(255,255,255,0.40)",
          "bg-dark": "rgba(255,255,255,0.06)",
          "border-dark": "rgba(255,255,255,0.12)",
        },
        // Brand scale — indigo/blue
        brand: {
          50:  "#eef4ff",
          100: "#dbe6fe",
          200: "#bfd3fe",
          300: "#93b4fd",
          400: "#5b8cff",
          500: "#3366ff",
          600: "#274bdb",
          700: "#1f3bb0",
          800: "#1e3285",
          900: "#1d2f6a",
        },
        // Semantic surface tokens (mapped to CSS vars in styles.css)
        surface: {
          DEFAULT: "var(--fl-surface)",
          raised: "var(--fl-surface-raised)",
          overlay: "var(--fl-surface-overlay)",
        },
        "on-surface": "var(--fl-on-surface)",
        "on-surface-muted": "var(--fl-on-surface-muted)",
        // Status colours
        success: {
          50:  "#f0fdf4",
          100: "#dcfce7",
          200: "#bbf7d0",
          300: "#86efac",
          400: "#4ade80",
          500: "#22c55e",
          600: "#16a34a",
          700: "#15803d",
          800: "#166534",
        },
        warning: {
          50:  "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
          800: "#92400e",
        },
        danger: {
          50:  "#fff1f2",
          100: "#ffe4e6",
          200: "#fecdd3",
          300: "#fda4af",
          400: "#fb7185",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
        },
        info: {
          50:  "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
        },
      },
      // Spacing scale extension
      spacing: {
        18: "4.5rem",
        22: "5.5rem",
        26: "6.5rem",
        30: "7.5rem",
      },
      // Border radius tokens
      borderRadius: {
        xl2: "1.25rem",
        xl3: "1.5rem",
        "4xl": "2rem",
      },
      // Backdrop blur tokens
      backdropBlur: {
        xs:  "2px",
        "2xl": "40px",
        "3xl": "64px",
      },
      // Shadow tokens
      boxShadow: {
        glass:     "0 8px 32px 0 rgba(31, 38, 135, 0.12)",
        "glass-md":"0 12px 40px 0 rgba(31, 38, 135, 0.18)",
        "glass-lg":"0 20px 60px 0 rgba(31, 38, 135, 0.22)",
        "glass-dark": "0 8px 32px 0 rgba(0, 0, 0, 0.40)",
        "glass-dark-md": "0 12px 40px 0 rgba(0, 0, 0, 0.50)",
        soft:      "0 2px 8px 0 rgba(0,0,0,0.06)",
        "soft-md": "0 4px 16px 0 rgba(0,0,0,0.08)",
        "card":    "0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(31,38,135,0.08)",
        "brand-glow": "0 0 20px rgba(51, 102, 255, 0.35)",
        "success-glow": "0 0 20px rgba(34, 197, 94, 0.30)",
        "inner-ring": "inset 0 0 0 1px rgba(255,255,255,0.25)",
        none: "none",
      },
      // Typography
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Display"',
          '"SF Pro Text"',
          '"Helvetica Neue"',
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: ['"SF Mono"', '"Fira Code"', '"Cascadia Code"', "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
      // Animation / keyframes
      keyframes: {
        "fade-in": {
          "0%":   { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-up": {
          "0%":   { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-out": {
          "0%":   { opacity: "1", transform: "translateY(0)" },
          "100%": { opacity: "0", transform: "translateY(-6px)" },
        },
        "slide-in-right": {
          "0%":   { opacity: "0", transform: "translateX(20px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-out-right": {
          "0%":   { opacity: "1", transform: "translateX(0)" },
          "100%": { opacity: "0", transform: "translateX(20px)" },
        },
        "scale-in": {
          "0%":   { opacity: "0", transform: "scale(0.94)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "shimmer": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-ring": {
          "0%":   { transform: "scale(0.95)", boxShadow: "0 0 0 0 rgba(51,102,255,0.4)" },
          "70%":  { transform: "scale(1)", boxShadow: "0 0 0 10px rgba(51,102,255,0)" },
          "100%": { transform: "scale(0.95)", boxShadow: "0 0 0 0 rgba(51,102,255,0)" },
        },
        "spin-slow": {
          "100%": { transform: "rotate(360deg)" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%":      { transform: "translateY(-6px)" },
        },
        "toast-in": {
          "0%":   { opacity: "0", transform: "translateX(calc(100% + 1rem))" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "toast-out": {
          "0%":   { opacity: "1", transform: "translateX(0)" },
          "100%": { opacity: "0", transform: "translateX(calc(100% + 1rem))" },
        },
      },
      animation: {
        "fade-in":          "fade-in 0.25s ease both",
        "fade-in-slow":     "fade-in 0.45s ease both",
        "fade-in-up":       "fade-in-up 0.35s ease both",
        "fade-out":         "fade-out 0.2s ease both",
        "slide-in-right":   "slide-in-right 0.3s cubic-bezier(0.16,1,0.3,1) both",
        "slide-out-right":  "slide-out-right 0.25s ease both",
        "scale-in":         "scale-in 0.2s cubic-bezier(0.16,1,0.3,1) both",
        "shimmer":          "shimmer 1.8s linear infinite",
        "pulse-ring":       "pulse-ring 1.5s cubic-bezier(0.455,0.03,0.515,0.955) infinite",
        "spin-slow":        "spin-slow 2s linear infinite",
        "float":            "float 3s ease-in-out infinite",
        "toast-in":         "toast-in 0.35s cubic-bezier(0.16,1,0.3,1) both",
        "toast-out":        "toast-out 0.25s ease both",
      },
      // Transition duration extension
      transitionDuration: {
        250: "250ms",
        350: "350ms",
        400: "400ms",
      },
      // Z-index scale for layered UI
      zIndex: {
        60: "60",
        70: "70",
        80: "80",
        90: "90",
        100: "100",
      },
    },
  },
  plugins: [],
  safelist: [
    // Non-standard white/black opacity values used in dark-mode glass effects.
    // Explicit list is more reliable than pattern for non-5-step opacities.
    'bg-white/6',   'dark:bg-white/6',
    'bg-white/8',   'dark:bg-white/8',   'hover:bg-white/8',   'dark:hover:bg-white/8',
    'bg-white/12',  'dark:bg-white/12',  'hover:bg-white/12',
    'bg-white/15',  'dark:bg-white/15',
    'border-white/8',  'dark:border-white/8',
    'border-white/12', 'dark:border-white/12',
    'bg-gray-200/60',  'border-gray-200/60',
  ],
};
