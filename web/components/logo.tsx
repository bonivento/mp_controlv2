import { BRAND_NAME } from "@/lib/brand";

/**
 * Isotipo de Sigmalena: una σ minúscula cuyo trazo superior se prolonga como la línea de un
 * gráfico de control entre dos límites punteados; el último punto, en naranja, sale del límite.
 * Es un dibujo original (no deriva del escudo de la universidad ni de otras marcas).
 *
 * Variantes:
 *  - "auto":   azul de marca sobre fondo claro y blanco sobre fondo oscuro (sigue el tema).
 *  - "onDark": siempre blanco con punto naranja (para fondos azules u oscuros).
 *  - "mono":   un solo color (el del texto actual), también el punto. Para impresión en B/N.
 *  - "tile":   baldosa azul con la σ en blanco (la misma del favicon).
 */
export type MarkVariant = "auto" | "onDark" | "mono" | "tile";

const GLYPH = (
  <>
    <circle cx="21" cy="38" r="10" strokeWidth="4.8" />
    <path d="M21 28H33" strokeWidth="4.8" />
    <path d="M33 28L38.5 36L43.5 28.5L48.5 35L54 12" strokeWidth="3" />
  </>
);

export function SigmalenaMark({
  variant = "auto",
  size = 32,
  title,
  className,
}: {
  variant?: MarkVariant;
  size?: number;
  /** Si se da, el dibujo se anuncia como imagen; si no, se oculta a los lectores de pantalla. */
  title?: string;
  className?: string;
}) {
  const tile = variant === "tile";
  const ink = variant === "auto" ? "var(--logo-ink)" : variant === "mono" ? "currentColor" : "#ffffff";
  const dot = variant === "mono" ? "currentColor" : "#FF9400";
  const limits = variant === "auto" ? "var(--logo-ink)" : ink;
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {tile && <rect width="64" height="64" rx="14" fill="#004A87" />}
      <path
        d={tile ? "M8 19H56M8 53H56" : "M4 19H60M4 53H60"}
        stroke={limits}
        strokeOpacity={tile ? 0.55 : 0.45}
        strokeWidth="1.6"
        strokeDasharray="2.5 3"
        fill="none"
      />
      <g fill="none" stroke={ink} strokeLinecap="round" strokeLinejoin="round">
        {GLYPH}
      </g>
      <circle cx="54" cy="12" r="5.2" fill={dot} />
    </svg>
  );
}

/**
 * Logotipo horizontal: isotipo + «Sigmalena». El texto es texto real (hereda la fuente y el
 * color de la interfaz): «Sigma» en peso fuerte y «lena» en peso medio.
 */
export function SigmalenaLogo({
  size = 32,
  variant = "auto",
  className = "",
  withText = true,
}: {
  size?: number;
  variant?: MarkVariant;
  className?: string;
  withText?: boolean;
}) {
  const color =
    variant === "onDark" ? "text-white" : variant === "mono" ? "text-current" : "text-[var(--logo-ink)]";
  return (
    <span className={`inline-flex items-center gap-2 leading-none ${className}`}>
      <SigmalenaMark variant={variant} size={size} title={withText ? undefined : BRAND_NAME} />
      {withText && (
        <span className={`${color} font-semibold tracking-tight`} style={{ fontSize: size * 0.62 }}>
          <span className="font-bold">Sigma</span>
          <span className="font-medium">lena</span>
        </span>
      )}
    </span>
  );
}
