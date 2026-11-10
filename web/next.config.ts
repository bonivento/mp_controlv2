import type { NextConfig } from "next";

// Dirección de la API de cálculo (FastAPI). El navegador siempre llama a /api/*
// en el mismo origen y este rewrite lo reenvía, así no hay CORS.
const apiUrl = (process.env.API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // La app es casi toda cliente (sesión y datos se leen en el navegador), así que no hay
  // contenido que validar como "navegación instantánea": solo se valida lo que lo pida.
  experimental: { instantInsights: { validationLevel: "manual-warning" } },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
