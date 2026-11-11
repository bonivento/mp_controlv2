// Interfaz única de acceso a datos y sesión. Las pantallas solo conocen esto;
// detrás hay Supabase (supabase-store.ts) o el modo de demostración local
// (demo-store.ts). Cambiar de uno a otro no toca ninguna pantalla.

import type {
  Analysis,
  AnalysisInput,
  ControlLimitsInput,
  ControlLimitsRow,
  Dataset,
  DatasetInput,
  SamplingPlan,
  SamplingPlanInput,
  Study,
  StudyInput,
} from "../db";

export interface AppUser {
  id: string;
  email: string;
}

export interface SignUpResult {
  user: AppUser | null;
  /** Supabase puede exigir confirmar el correo antes de iniciar sesión. */
  needsConfirmation: boolean;
}

export interface DataStore {
  mode: "supabase" | "demo";
  auth: {
    getUser(): Promise<AppUser | null>;
    signUp(email: string, password: string): Promise<SignUpResult>;
    signIn(email: string, password: string): Promise<AppUser>;
    signOut(): Promise<void>;
    /** Avisa de cambios de sesión; devuelve la función para cancelar. */
    onChange(cb: (user: AppUser | null) => void): () => void;
    /** JWT para `Authorization: Bearer` en las llamadas a /api/*. */
    getAccessToken(): Promise<string | null>;
  };
  studies: {
    list(): Promise<Study[]>;
    get(id: string): Promise<Study | null>;
    create(input: StudyInput): Promise<Study>;
    update(id: string, patch: Partial<StudyInput>): Promise<Study>;
    remove(id: string): Promise<void>;
  };
  datasets: {
    list(studyId: string): Promise<Dataset[]>;
    get(id: string): Promise<Dataset | null>;
    create(input: DatasetInput): Promise<Dataset>;
    remove(id: string): Promise<void>;
  };
  controlLimits: {
    /** Límites vigentes del estudio (uno por tipo de gráfico). */
    listActive(studyId: string): Promise<ControlLimitsRow[]>;
    /** Desactiva los vigentes del mismo tipo e inserta los nuevos. */
    freeze(input: ControlLimitsInput): Promise<ControlLimitsRow>;
  };
  analyses: {
    list(studyId: string): Promise<Analysis[]>;
    create(input: AnalysisInput): Promise<Analysis>;
    setInReport(id: string, inReport: boolean): Promise<void>;
    remove(id: string): Promise<void>;
  };
  samplingPlans: {
    list(studyId: string): Promise<SamplingPlan[]>;
    create(input: SamplingPlanInput): Promise<SamplingPlan>;
    remove(id: string): Promise<void>;
  };
}
