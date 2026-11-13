import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/components/auth-provider";
import { SiteFooter } from "@/components/site-footer";
import { BRAND_DESCRIPTION, BRAND_NAME, BRAND_TITLE } from "@/lib/brand";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  // Base para las URL absolutas de Open Graph. En Vercel Next usa la URL de producción si no se define.
  ...(process.env.NEXT_PUBLIC_SITE_URL ? { metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL) } : {}),
  applicationName: BRAND_NAME,
  title: { default: BRAND_TITLE, template: `%s · ${BRAND_NAME}` },
  description: BRAND_DESCRIPTION,
  openGraph: {
    type: "website",
    siteName: BRAND_NAME,
    locale: "es_CO",
    title: BRAND_TITLE,
    description: BRAND_DESCRIPTION,
  },
  twitter: { card: "summary_large_image", title: BRAND_TITLE, description: BRAND_DESCRIPTION },
};

// Color de la barra del navegador en móvil: el azul base de la paleta (claro) y su paso profundo (oscuro).
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#004A87" },
    { media: "(prefers-color-scheme: dark)", color: "#00294B" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
        >
          Saltar al contenido
        </a>
        <AuthProvider>{children}</AuthProvider>
        <SiteFooter />
      </body>
    </html>
  );
}
