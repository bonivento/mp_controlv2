declare module "plotly.js-basic-dist-min" {
  const Plotly: {
    downloadImage(
      gd: HTMLElement,
      opts: { format: "png" | "svg" | "jpeg" | "webp"; filename?: string; width?: number; height?: number; scale?: number },
    ): Promise<string>;
    /** Acepta un elemento o una figura {data, layout}; devuelve una URL de datos. */
    toImage(
      figure: HTMLElement | { data: unknown[]; layout: unknown },
      opts: { format: "png" | "svg" | "jpeg" | "webp"; width?: number; height?: number; scale?: number },
    ): Promise<string>;
    Plots: { resize(gd: HTMLElement): Promise<unknown> };
  };
  export default Plotly;
}
