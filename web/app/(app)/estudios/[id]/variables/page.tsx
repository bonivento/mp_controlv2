"use client";

import { ChartWorkbench } from "@/components/charts/ChartWorkbench";
import { useStudy } from "@/components/study-context";
import { Alert } from "@/components/ui";

export default function VariablesPage() {
  const { study } = useStudy();
  if (study.data_type !== "variable")
    return <Alert tone="warn" title="Este estudio es por atributos">Usa el módulo Atributos.</Alert>;
  return <ChartWorkbench kind="variables" />;
}
