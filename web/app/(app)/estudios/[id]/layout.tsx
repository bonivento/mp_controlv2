import { Suspense } from "react";
import { StudyShell } from "@/components/study-context";
import { Loading } from "@/components/ui";

export default function StudyLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<Loading label="Cargando estudio…" />}>
      <StudyShell>{children}</StudyShell>
    </Suspense>
  );
}
