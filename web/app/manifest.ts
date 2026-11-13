import type { MetadataRoute } from "next";
import { BRAND_DESCRIPTION, BRAND_DESCRIPTOR, BRAND_NAME } from "@/lib/brand";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${BRAND_NAME} · ${BRAND_DESCRIPTOR}`,
    short_name: BRAND_NAME,
    description: BRAND_DESCRIPTION,
    lang: "es",
    start_url: "/estudios",
    display: "standalone",
    background_color: "#f3f6fa",
    theme_color: "#004A87",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
