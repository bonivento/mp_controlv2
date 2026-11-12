"use client";

import { useState } from "react";
import type { SizeIssue } from "@/lib/dataset-utils";
import { Alert, Button, Card, Modal, Table, Td, TextAreaField, Th } from "../ui";

export interface IncompleteDecision {
  kind: "incomplete";
  label: string;
  /** Tamaño que tenía el subgrupo. */
  n: number;
  /** Tamaño predominante del conjunto. */
  expected: number;
  justification: string;
}

/**
 * Subgrupos con un tamaño distinto del predominante (p. ej. por celdas vacías). X-barra los
 * rechaza. Se pueden retirar, uno a uno o todos, con una justificación que va a la bitácora de
 * limpieza. No se rellenan valores faltantes: inventar datos distorsiona los límites.
 */
export function IncompleteSubgroups({
  issue,
  onRetire,
}: {
  issue: SizeIssue;
  onRetire: (decisions: IncompleteDecision[]) => void;
}) {
  const [target, setTarget] = useState<"all" | number | null>(null);
  const [why, setWhy] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const picked = target === "all" ? issue.items : issue.items.filter((x) => x.index === target);

  function confirm() {
    if (why.trim().length < 5) {
      setErr("Escribe la justificación (al menos 5 caracteres).");
      return;
    }
    onRetire(picked.map((x) => ({ kind: "incomplete", label: x.label, n: x.n, expected: issue.predominant, justification: why.trim() })));
    setTarget(null);
    setWhy("");
    setErr(null);
  }

  return (
    <Card
      title={`Subgrupos incompletos (${issue.items.length})`}
      actions={
        issue.items.length > 1 ? (
          <Button onClick={() => { setTarget("all"); setWhy(""); setErr(null); }}>Retirar todos…</Button>
        ) : undefined
      }
    >
      <Alert tone="warn" title={`El tamaño predominante es n = ${issue.predominant}`}>
        Estos subgrupos tienen otro tamaño, normalmente por celdas vacías o no numéricas. X-barra necesita subgrupos del mismo tamaño y no
        puede usarlos así. La aplicación no rellena valores faltantes: puedes retirar el subgrupo completo, con justificación, o dejarlo si
        vas a usar otro gráfico.
      </Alert>
      <div className="mt-3">
        <Table caption="Subgrupos con tamaño distinto del predominante">
          <thead>
            <tr><Th>Subgrupo</Th><Th>n</Th><Th>Faltan</Th><Th>Acción</Th></tr>
          </thead>
          <tbody>
            {issue.items.map((x) => (
              <tr key={`${x.label}-${x.index}`}>
                <Td className="font-medium">{x.label}</Td>
                <Td>{x.n}</Td>
                <Td>{x.n < issue.predominant ? issue.predominant - x.n : `sobran ${x.n - issue.predominant}`}</Td>
                <Td>
                  <Button onClick={() => { setTarget(x.index); setWhy(""); setErr(null); }} aria-label={`Retirar el subgrupo ${x.label}`}>
                    Retirar…
                  </Button>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>

      <Modal open={target != null} title="Retirar subgrupos incompletos" onClose={() => setTarget(null)}>
        {target != null && (
          <div className="flex flex-col gap-3 text-sm">
            <p>
              Se {picked.length === 1 ? "retirará el subgrupo" : "retirarán los subgrupos"}{" "}
              <strong>{picked.map((x) => `${x.label} (n = ${x.n})`).join(", ")}</strong> del conjunto de datos. Los demás no cambian.
            </p>
            <TextAreaField
              label="Justificación (obligatoria)"
              value={why}
              error={err ?? undefined}
              onChange={(e) => setWhy(e.target.value)}
              hint="Queda en la bitácora de limpieza del conjunto de datos."
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button onClick={() => setTarget(null)}>Cancelar</Button>
              <Button variant="primary" onClick={confirm}>Retirar y registrar</Button>
            </div>
          </div>
        )}
      </Modal>
    </Card>
  );
}
