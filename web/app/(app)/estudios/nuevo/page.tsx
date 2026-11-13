"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { StudyForm } from "@/components/study-form";
import { Card, PageHeader } from "@/components/ui";
import { getStore } from "@/lib/data";

export default function NewStudyPage() {
  const router = useRouter();
  return (
    <>
      <title>Nuevo estudio · Sigmalena</title>
      <p className="mb-2 text-sm">
        <Link href="/estudios" className="text-brand-text hover:underline">
          ← Estudios
        </Link>
      </p>
      <PageHeader title="Nuevo estudio" subtitle="Describe el proceso y la característica de calidad que vas a controlar." />
      <Card>
        <StudyForm
          submitLabel="Crear estudio"
          onCancel={() => router.push("/estudios")}
          onSubmit={async (v) => {
            const s = await getStore().studies.create(v);
            router.push(`/estudios/${s.id}`);
          }}
        />
      </Card>
    </>
  );
}
