declare module "plotly.js-basic-dist-min" {
  const Plotly: {
    downloadImage(
      gd: HTMLElement,
      opts: { format: "png" | "svg" | "jpeg" | "webp"; filename?: string; width?: number; height?: number; scale?: number },
    ): Promise<string>;
  };
  export default Plotly;
}
