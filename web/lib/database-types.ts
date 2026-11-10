export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

// ESCRITO A MANO con la forma exacta que produce `supabase gen types typescript`.
// No se generó con la CLI porque Docker no estaba disponible. Regenerar con:
//   npx supabase gen types typescript --local > web/lib/database-types.ts   (ver supabase/README.md)

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.1"
  }
  public: {
    Tables: {
      studies: {
        Row: {
          id: string
          user_id: string
          name: string
          company: string | null
          process: string | null
          product: string | null
          characteristic: string | null
          unit: string | null
          data_type: string
          lsl: number | null
          usl: number | null
          target: number | null
          notes: string | null
          is_synthetic: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id?: string
          name: string
          company?: string | null
          process?: string | null
          product?: string | null
          characteristic?: string | null
          unit?: string | null
          data_type: string
          lsl?: number | null
          usl?: number | null
          target?: number | null
          notes?: string | null
          is_synthetic?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          company?: string | null
          process?: string | null
          product?: string | null
          characteristic?: string | null
          unit?: string | null
          data_type?: string
          lsl?: number | null
          usl?: number | null
          target?: number | null
          notes?: string | null
          is_synthetic?: boolean
          created_at?: string
          updated_at?: string
        }
        Relationships: [
        ]
      }
      datasets: {
        Row: {
          id: string
          user_id: string
          study_id: string
          name: string
          phase: string
          source_file: string | null
          subgrouping: Json
          rows: Json
          cleaning_log: Json
          created_at: string
        }
        Insert: {
          id?: string
          user_id?: string
          study_id: string
          name: string
          phase: string
          source_file?: string | null
          subgrouping?: Json
          rows: Json
          cleaning_log?: Json
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          study_id?: string
          name?: string
          phase?: string
          source_file?: string | null
          subgrouping?: Json
          rows?: Json
          cleaning_log?: Json
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "datasets_study_owner_fkey"
            columns: ["study_id", "user_id"]
            isOneToOne: false
            referencedRelation: "studies"
            referencedColumns: ["id", "user_id"]
          },
        ]
      }
      control_limits: {
        Row: {
          id: string
          user_id: string
          study_id: string
          dataset_id: string | null
          chart_type: string
          limits: Json
          is_active: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id?: string
          study_id: string
          dataset_id?: string | null
          chart_type: string
          limits: Json
          is_active?: boolean
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          study_id?: string
          dataset_id?: string | null
          chart_type?: string
          limits?: Json
          is_active?: boolean
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "control_limits_study_owner_fkey"
            columns: ["study_id", "user_id"]
            isOneToOne: false
            referencedRelation: "studies"
            referencedColumns: ["id", "user_id"]
          },
          {
            foreignKeyName: "control_limits_dataset_study_fkey"
            columns: ["dataset_id", "study_id"]
            isOneToOne: false
            referencedRelation: "datasets"
            referencedColumns: ["id", "study_id"]
          },
        ]
      }
      analyses: {
        Row: {
          id: string
          user_id: string
          study_id: string
          dataset_id: string | null
          module: string
          title: string
          params: Json
          result: Json
          in_report: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id?: string
          study_id: string
          dataset_id?: string | null
          module: string
          title: string
          params: Json
          result: Json
          in_report?: boolean
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          study_id?: string
          dataset_id?: string | null
          module?: string
          title?: string
          params?: Json
          result?: Json
          in_report?: boolean
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "analyses_study_owner_fkey"
            columns: ["study_id", "user_id"]
            isOneToOne: false
            referencedRelation: "studies"
            referencedColumns: ["id", "user_id"]
          },
          {
            foreignKeyName: "analyses_dataset_study_fkey"
            columns: ["dataset_id", "study_id"]
            isOneToOne: false
            referencedRelation: "datasets"
            referencedColumns: ["id", "study_id"]
          },
        ]
      }
      sampling_plans: {
        Row: {
          id: string
          user_id: string
          study_id: string
          name: string
          plan_type: string
          params: Json
          result: Json
          created_at: string
        }
        Insert: {
          id?: string
          user_id?: string
          study_id: string
          name: string
          plan_type: string
          params: Json
          result: Json
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          study_id?: string
          name?: string
          plan_type?: string
          params?: Json
          result?: Json
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "sampling_plans_study_owner_fkey"
            columns: ["study_id", "user_id"]
            isOneToOne: false
            referencedRelation: "studies"
            referencedColumns: ["id", "user_id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DefaultSchema = Database[Extract<keyof Database, "public">]

export type Tables<
  TableName extends keyof DefaultSchema["Tables"],
> = DefaultSchema["Tables"][TableName]["Row"]

export type TablesInsert<
  TableName extends keyof DefaultSchema["Tables"],
> = DefaultSchema["Tables"][TableName]["Insert"]

export type TablesUpdate<
  TableName extends keyof DefaultSchema["Tables"],
> = DefaultSchema["Tables"][TableName]["Update"]

export const Constants = {
  public: {
    Enums: {},
  },
} as const
