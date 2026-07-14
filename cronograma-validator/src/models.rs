#![allow(dead_code)]
use chrono::{NaiveDate, NaiveDateTime, NaiveTime};
use serde::Serialize;

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct WorkOrder {
    pub id: i32,
    pub codigo_de_orden: Option<String>,
    pub tipo: String,
    pub estado: String,
    pub prioridad: String,
    pub inicio_programado: Option<NaiveDateTime>,
    pub fin_programado: Option<NaiveDateTime>,
    pub rutina_id: Option<i32>,
    pub programacion_id: Option<i32>,
    pub tecnico_id: Option<i32>,
    pub ubicacion_id: Option<i32>,
    pub fecha_ejecucion: Option<NaiveDateTime>,
}

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct WorkOrderWithDetails {
    pub id: i32,
    pub codigo_de_orden: Option<String>,
    pub tipo: String,
    pub estado: String,
    pub prioridad: String,
    pub inicio_programado: Option<NaiveDateTime>,
    pub fin_programado: Option<NaiveDateTime>,
    pub rutina_nombre: Option<String>,
    pub programacion_id: Option<i32>,
    pub tecnico_nombre: Option<String>,
    pub tecnico_id: Option<i32>,
    pub ubicacion_nombre: Option<String>,
    pub activo_nombres: Option<String>,
}

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct Schedule {
    pub id: i32,
    pub nombre: String,
    pub color: String,
}

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct DaySchedule {
    pub horario_id: i32,
    pub dia: i32,
    pub hora_inicio: NaiveTime,
    pub hora_fin: NaiveTime,
}

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct CalendarRestriction {
    pub fecha: NaiveDate,
    pub motivo: String,
}

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct Programming {
    pub id: i32,
    pub rutina_id: i32,
    pub fecha_inicio: NaiveDate,
    pub fecha_fin: Option<NaiveDate>,
    pub procesada: bool,
}

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct Routine {
    pub id: i32,
    pub nombre: Option<String>,
    pub frecuencia_id: Option<i32>,
    pub cantidad_tecnicos: Option<i32>,
}

#[derive(Debug, Clone, sqlx::FromRow, Serialize)]
pub struct Frequency {
    pub id: i32,
    pub nombre: String,
    pub dias: i32,
}

#[derive(Debug, Clone, Serialize)]
pub struct ValidationIssue {
    pub severity: Severity,
    pub category: IssueCategory,
    pub message: String,
    pub order_id: Option<i32>,
    pub codigo: Option<String>,
    pub technician: Option<String>,
    pub location: Option<String>,
    pub detail: String,
}

#[derive(Debug, Clone, Serialize)]
pub enum Severity {
    Error,
    Warning,
    Info,
}

impl std::fmt::Display for Severity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Severity::Error => write!(f, "ERROR"),
            Severity::Warning => write!(f, "WARNING"),
            Severity::Info => write!(f, "INFO"),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub enum IssueCategory {
    TechnicianOverlap,
    AssetOverlap,
    OutsideWorkingHours,
    OnRestrictedDate,
    FrequencyViolation,
    MissingTechnician,
    MissingSchedule,
    MissingLocation,
    InconsistentState,
    DurationMismatch,
    DateOrder,
}

impl std::fmt::Display for IssueCategory {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IssueCategory::TechnicianOverlap => write!(f, "Solapamiento Técnico"),
            IssueCategory::AssetOverlap => write!(f, "Solapamiento Activo"),
            IssueCategory::OutsideWorkingHours => write!(f, "Fuera de Horario Laboral"),
            IssueCategory::OnRestrictedDate => write!(f, "Fecha Restringida"),
            IssueCategory::FrequencyViolation => write!(f, "Violación de Frecuencia"),
            IssueCategory::MissingTechnician => write!(f, "Técnico No Asignado"),
            IssueCategory::MissingSchedule => write!(f, "Sin Horario"),
            IssueCategory::MissingLocation => write!(f, "Sin Ubicación"),
            IssueCategory::InconsistentState => write!(f, "Estado Inconsistente"),
            IssueCategory::DurationMismatch => write!(f, "Duración Incorrecta"),
            IssueCategory::DateOrder => write!(f, "Orden de Fechas"),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct ValidationSummary {
    pub total_orders: usize,
    pub total_issues: usize,
    pub errors: usize,
    pub warnings: usize,
    pub info: usize,
    pub by_category: Vec<CategoryCount>,
    pub by_severity: Vec<SeverityCount>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CategoryCount {
    pub category: String,
    pub count: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct SeverityCount {
    pub severity: String,
    pub count: usize,
}
