"use client";

import { ChartWorkbench } from "@/components/charts/ChartWorkbench";
import { useStudy } from "@/components/study-context";
import { Alert } from "@/components/ui";

export default function AttributesPage() {
  const { study } = useStudy();
  if (study.data_type !== "attribute")
    return <Alert tone="warn" title="Este estudio es por variables">Usa el módulo Variables.</Alert>;
  return <ChartWorkbench kind="attributes" />;
}
