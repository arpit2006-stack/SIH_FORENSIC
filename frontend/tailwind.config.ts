import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "rgb(var(--bg-primary) / <alpha-value>)",
        surface: "rgb(var(--bg-surface) / <alpha-value>)",
        textPrimary: "rgb(var(--text-primary) / <alpha-value>)",
        textSecondary: "rgb(var(--text-secondary) / <alpha-value>)",
        danger: "rgb(var(--accent-danger) / <alpha-value>)",
        safe: "rgb(var(--accent-safe) / <alpha-value>)",
        success: "rgb(var(--accent-success) / <alpha-value>)",
        warning: "rgb(var(--accent-warning) / <alpha-value>)",
        neutral: "rgb(var(--accent-neutral) / <alpha-value>)",
      },
      backgroundColor: {
        primary: "rgb(var(--bg-primary) / <alpha-value>)",
        surface: "rgb(var(--bg-surface) / <alpha-value>)",
      },
      textColor: {
        primary: "rgb(var(--text-primary) / <alpha-value>)",
        secondary: "rgb(var(--text-secondary) / <alpha-value>)",
      }
    },
  },
  plugins: [],
};
export default config;
