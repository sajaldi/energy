use std::collections::{HashMap, HashSet};
use chrono::{NaiveDate, Duration, Datelike};
use crate::models::*;

pub struct Validator;

impl Validator {
    pub fn validate_all(
        orders: &[WorkOrderWithDetails],
        raw_orders: &[WorkOrder],
        _schedules: &[Schedule],
        day_schedules: &[DaySchedule],
        restrictions: &[CalendarRestriction],
        frequencies: &[Frequency],
        routines: &[Routine],
    ) -> Vec<ValidationIssue> {
        let mut issues = Vec::new();

        let restriction_dates: HashSet<NaiveDate> =
            restrictions.iter().map(|r| r.fecha).collect();

        let schedule_map: HashMap<i32, Vec<DaySchedule>> = {
            let mut map: HashMap<i32, Vec<DaySchedule>> = HashMap::new();
            for ds in day_schedules {
                map.entry(ds.horario_id).or_default().push(ds.clone());
            }
            map
        };

        let freq_map: HashMap<i32, i32> =
            frequencies.iter().map(|f| (f.id, f.dias)).collect();

        let routine_map: HashMap<i32, &Routine> =
            routines.iter().map(|r| (r.id, r)).collect();

        Self::check_technician_overlaps(&mut issues, orders);
        Self::check_missing_technician(&mut issues, orders);
        Self::check_missing_location(&mut issues, orders);
        Self::check_outside_working_hours(&mut issues, orders, &schedule_map, &restriction_dates);
        Self::check_restricted_dates(&mut issues, orders, &restriction_dates);
        Self::check_date_order(&mut issues, orders);
        Self::check_inconsistent_state(&mut issues, orders);
        Self::check_frequency_violations(&mut issues, raw_orders, &freq_map, &routine_map);

        issues
    }

    fn check_technician_overlaps(issues: &mut Vec<ValidationIssue>, orders: &[WorkOrderWithDetails]) {
        let mut by_tech: HashMap<Option<i32>, Vec<&WorkOrderWithDetails>> = HashMap::new();
        for o in orders {
            by_tech.entry(o.tecnico_id).or_default().push(o);
        }

        for (_tech_id, tech_orders) in &by_tech {
            let label = tech_orders
                .first()
                .and_then(|o| o.tecnico_nombre.as_deref())
                .unwrap_or("(sin técnico)");
            for i in 0..tech_orders.len() {
                for j in (i + 1)..tech_orders.len() {
                    let a = tech_orders[i];
                    let b = tech_orders[j];
                    if let (Some(ai), Some(af), Some(bi), Some(bf)) =
                        (a.inicio_programado, a.fin_programado, b.inicio_programado, b.fin_programado)
                    {
                        if ai < bf && bi < af {
                            issues.push(ValidationIssue {
                                severity: Severity::Error,
                                category: IssueCategory::TechnicianOverlap,
                                message: format!(
                                    "Técnico '{}' tiene órdenes superpuestas",
                                    label
                                ),
                                order_id: Some(a.id),
                                codigo: a.codigo_de_orden.clone(),
                                technician: Some(label.to_string()),
                                location: a.ubicacion_nombre.clone(),
                                detail: format!(
                                    "OT#{} '{}' [{} - {}] se solapa con OT#{} '{}' [{} - {}]",
                                    a.id,
                                    a.codigo_de_orden.as_deref().unwrap_or("N/A"),
                                    ai.format("%Y-%m-%d %H:%M"),
                                    af.format("%H:%M"),
                                    b.id,
                                    b.codigo_de_orden.as_deref().unwrap_or("N/A"),
                                    bi.format("%Y-%m-%d %H:%M"),
                                    bf.format("%H:%M"),
                                ),
                            });
                        }
                    }
                }
            }
        }
    }

    fn check_missing_technician(issues: &mut Vec<ValidationIssue>, orders: &[WorkOrderWithDetails]) {
        for o in orders {
            if o.tecnico_id.is_none() && (o.estado == "PROGRAMADA" || o.estado == "EJECUCION") {
                issues.push(ValidationIssue {
                    severity: Severity::Warning,
                    category: IssueCategory::MissingTechnician,
                    message: "Orden sin técnico asignado".to_string(),
                    order_id: Some(o.id),
                    codigo: o.codigo_de_orden.clone(),
                    technician: None,
                    location: o.ubicacion_nombre.clone(),
                    detail: format!(
                        "OT#{} '{}' en estado '{}' no tiene técnico asignado",
                        o.id,
                        o.codigo_de_orden.as_deref().unwrap_or("N/A"),
                        o.estado,
                    ),
                });
            }
        }
    }

    fn check_missing_location(issues: &mut Vec<ValidationIssue>, orders: &[WorkOrderWithDetails]) {
        for o in orders {
            if o.ubicacion_nombre.is_none() {
                issues.push(ValidationIssue {
                    severity: Severity::Warning,
                    category: IssueCategory::MissingLocation,
                    message: "Orden sin ubicación".to_string(),
                    order_id: Some(o.id),
                    codigo: o.codigo_de_orden.clone(),
                    technician: o.tecnico_nombre.clone(),
                    location: None,
                    detail: format!(
                        "OT#{} '{}' no tiene ubicación asignada",
                        o.id,
                        o.codigo_de_orden.as_deref().unwrap_or("N/A"),
                    ),
                });
            }
        }
    }

    fn check_outside_working_hours(
        issues: &mut Vec<ValidationIssue>,
        orders: &[WorkOrderWithDetails],
        schedule_map: &HashMap<i32, Vec<DaySchedule>>,
        restrictions: &HashSet<NaiveDate>,
    ) {
        for o in orders {
            let start = match o.inicio_programado {
                Some(s) => s,
                None => continue,
            };
            let end = match o.fin_programado {
                Some(e) => e,
                None => continue,
            };

            if restrictions.contains(&start.date()) {
                continue;
            }

            let day_schedules: Vec<&DaySchedule> = schedule_map
                .values()
                .flatten()
                .filter(|ds| ds.dia == start.weekday().num_days_from_monday() as i32)
                .collect();

            if day_schedules.is_empty() {
                continue;
            }

            let within = day_schedules.iter().any(|ds| {
                let s_time = start.time();
                let e_time = end.time();
                let work_start = ds.hora_inicio;
                let mut work_end = ds.hora_fin;
                if work_end <= work_start {
                    work_end = work_end + Duration::hours(24);
                }
                s_time >= work_start && e_time <= work_end
            });

            if !within {
                let ds = day_schedules[0];
                issues.push(ValidationIssue {
                    severity: Severity::Warning,
                    category: IssueCategory::OutsideWorkingHours,
                    message: "Orden fuera del horario laboral".to_string(),
                    order_id: Some(o.id),
                    codigo: o.codigo_de_orden.clone(),
                    technician: o.tecnico_nombre.clone(),
                    location: o.ubicacion_nombre.clone(),
                    detail: format!(
                        "OT#{} '{}' programada [{} - {}] fuera del horario laboral [{:?} - {:?}]",
                        o.id,
                        o.codigo_de_orden.as_deref().unwrap_or("N/A"),
                        start.format("%H:%M"),
                        end.format("%H:%M"),
                        ds.hora_inicio,
                        ds.hora_fin,
                    ),
                });
            }
        }
    }

    fn check_restricted_dates(
        issues: &mut Vec<ValidationIssue>,
        orders: &[WorkOrderWithDetails],
        restrictions: &HashSet<NaiveDate>,
    ) {
        for o in orders {
            let start = match o.inicio_programado {
                Some(s) => s,
                None => continue,
            };
            if restrictions.contains(&start.date()) {
                issues.push(ValidationIssue {
                    severity: Severity::Error,
                    category: IssueCategory::OnRestrictedDate,
                    message: "Orden en fecha restringida".to_string(),
                    order_id: Some(o.id),
                    codigo: o.codigo_de_orden.clone(),
                    technician: o.tecnico_nombre.clone(),
                    location: o.ubicacion_nombre.clone(),
                    detail: format!(
                        "OT#{} '{}' programada el {} - Fecha restringida en calendario",
                        o.id,
                        o.codigo_de_orden.as_deref().unwrap_or("N/A"),
                        start.date(),
                    ),
                });
            }
        }
    }

    fn check_date_order(issues: &mut Vec<ValidationIssue>, orders: &[WorkOrderWithDetails]) {
        for o in orders {
            if let (Some(start), Some(end)) = (o.inicio_programado, o.fin_programado) {
                if start > end {
                    issues.push(ValidationIssue {
                        severity: Severity::Error,
                        category: IssueCategory::DateOrder,
                        message: "La fecha de inicio es posterior a la fecha de fin".to_string(),
                        order_id: Some(o.id),
                        codigo: o.codigo_de_orden.clone(),
                        technician: o.tecnico_nombre.clone(),
                        location: o.ubicacion_nombre.clone(),
                        detail: format!(
                            "OT#{} '{}': inicio {} > fin {}",
                            o.id,
                            o.codigo_de_orden.as_deref().unwrap_or("N/A"),
                            start,
                            end,
                        ),
                    });
                }
            }
        }
    }

    fn check_inconsistent_state(issues: &mut Vec<ValidationIssue>, orders: &[WorkOrderWithDetails]) {
        for o in orders {
            if o.estado == "REALIZADA" && o.fin_programado.is_none() {
                issues.push(ValidationIssue {
                    severity: Severity::Error,
                    category: IssueCategory::InconsistentState,
                    message: "Orden REALIZADA sin fecha de fin programado".to_string(),
                    order_id: Some(o.id),
                    codigo: o.codigo_de_orden.clone(),
                    technician: o.tecnico_nombre.clone(),
                    location: o.ubicacion_nombre.clone(),
                    detail: format!(
                        "OT#{} '{}' está REALIZADA pero no tiene fin_programado",
                        o.id,
                        o.codigo_de_orden.as_deref().unwrap_or("N/A"),
                    ),
                });
            }
            if o.estado == "ESPERA" && o.inicio_programado.is_some() {
                issues.push(ValidationIssue {
                    severity: Severity::Info,
                    category: IssueCategory::InconsistentState,
                    message: "Orden en ESPERA con fecha programada".to_string(),
                    order_id: Some(o.id),
                    codigo: o.codigo_de_orden.clone(),
                    technician: o.tecnico_nombre.clone(),
                    location: o.ubicacion_nombre.clone(),
                    detail: format!(
                        "OT#{} '{}' está en ESPERA pero tiene inicio_programado = {}",
                        o.id,
                        o.codigo_de_orden.as_deref().unwrap_or("N/A"),
                        o.inicio_programado.unwrap(),
                    ),
                });
            }
        }
    }

    fn check_frequency_violations(
        issues: &mut Vec<ValidationIssue>,
        orders: &[WorkOrder],
        freq_map: &HashMap<i32, i32>,
        routine_map: &HashMap<i32, &Routine>,
    ) {
        let mut by_prog_asset: HashMap<(Option<i32>, Option<i32>), Vec<&WorkOrder>> = HashMap::new();
        for o in orders {
            let key = (o.programacion_id, o.ubicacion_id);
            by_prog_asset.entry(key).or_default().push(o);
        }

        for ((_prog_id, _), group_orders) in &by_prog_asset {
            if group_orders.len() < 2 {
                continue;
            }

            let rutina_id = match group_orders.first().and_then(|o| o.rutina_id) {
                Some(id) => id,
                None => continue,
            };

            let freq_dias = match routine_map.get(&rutina_id) {
                Some(r) => r.frecuencia_id.and_then(|fid| freq_map.get(&fid).copied()),
                None => None,
            };
            let freq_dias = match freq_dias {
                Some(d) => d,
                None => continue,
            };

            let mut sorted: Vec<&WorkOrder> = group_orders
                .iter()
                .filter(|o| o.inicio_programado.is_some())
                .copied()
                .collect();
            sorted.sort_by_key(|o| o.inicio_programado);

            for pair in sorted.windows(2) {
                let a = pair[0];
                let b = pair[1];
                if let (Some(ai), Some(bi)) = (a.inicio_programado, b.inicio_programado) {
                    let diff_days = (bi - ai).num_days().abs();
                    let margin = (freq_dias as f64 * 0.2).ceil() as i64;
                    if diff_days > 0 && diff_days < (freq_dias as i64 - margin).max(1) {
                        issues.push(ValidationIssue {
                            severity: Severity::Warning,
                            category: IssueCategory::FrequencyViolation,
                            message: format!(
                                "Órdenes demasiado próximas (frecuencia: {} días, diff: {} días)",
                                freq_dias, diff_days
                            ),
                            order_id: Some(b.id),
                            codigo: b.codigo_de_orden.clone(),
                            technician: None,
                            location: None,
                            detail: format!(
                                "OT#{} ({}) y OT#{} ({}) separadas por {} días, frecuencia esperada {} días",
                                a.id,
                                a.codigo_de_orden.as_deref().unwrap_or("N/A"),
                                b.id,
                                b.codigo_de_orden.as_deref().unwrap_or("N/A"),
                                diff_days,
                                freq_dias,
                            ),
                        });
                    }
                }
            }
        }
    }

    pub fn compute_summary(issues: &[ValidationIssue], orders: &[WorkOrderWithDetails]) -> ValidationSummary {
        let errors = issues.iter().filter(|i| matches!(i.severity, Severity::Error)).count();
        let warnings = issues.iter().filter(|i| matches!(i.severity, Severity::Warning)).count();
        let info = issues.iter().filter(|i| matches!(i.severity, Severity::Info)).count();

        let mut cat_map: HashMap<String, usize> = HashMap::new();
        for i in issues {
            *cat_map.entry(i.category.to_string()).or_default() += 1;
        }
        let mut by_category: Vec<CategoryCount> = cat_map
            .into_iter()
            .map(|(k, v)| CategoryCount { category: k, count: v })
            .collect();
        by_category.sort_by(|a, b| b.count.cmp(&a.count));

        let by_severity = vec![
            SeverityCount { severity: "ERROR".into(), count: errors },
            SeverityCount { severity: "WARNING".into(), count: warnings },
            SeverityCount { severity: "INFO".into(), count: info },
        ];

        ValidationSummary {
            total_orders: orders.len(),
            total_issues: issues.len(),
            errors,
            warnings,
            info,
            by_category,
            by_severity,
        }
    }
}
