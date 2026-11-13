"use client";

import { useRouter } from "next/navigation";
import { StudyForm } from "@/components/study-form";
import { useStudy } from "@/components/study-context";
import { Card, PageHeader } from "@/components/ui";
import { getStore } from "@/lib/data";

export default function EditStudyPage() {
  const { study, refresh } = useStudy();
  const router = useRouter();
  return (
    <>
      <title>{`Editar ${study.name} · Sigmalena`}</title>
      <PageHeader title="Editar estudio" />
      <Card>
        <StudyForm
          initial={study}
          submitLabel="Guardar cambios"
          onCancel={() => router.push(`/estudios/${study.id}`)}
          onSubmit={async (v) => {
            await getStore().studies.update(study.id, v);
            refresh();
            router.push(`/estudios/${study.id}`);
          }}
        />
      </Card>
    </>
  );
}
