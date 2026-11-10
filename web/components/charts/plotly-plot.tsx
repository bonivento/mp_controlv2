"use client";

// Se importa solo en el cliente (ver PlotlyChart): plotly.js necesita el DOM.
import Plotly from "plotly.js-basic-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

export const Plot = createPlotlyComponent(Plotly);
export const plotly = Plotly;
