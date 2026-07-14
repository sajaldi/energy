use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};
use crate::models::*;

pub async fn connect(database_url: &str) -> Result<PgPool, sqlx::Error> {
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(database_url)
        .await?;
    Ok(pool)
}

pub async fn fetch_work_orders(pool: &PgPool, days_back: i64) -> Result<Vec<WorkOrderWithDetails>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            ot.id,
            ot.codigo_de_orden,
            ot.tipo,
            ot.estado,
            ot.prioridad,
            ot.inicio_programado,
            ot.fin_programado,
            r.nombre AS rutina_nombre,
            ot.programacion_id,
            u.username AS tecnico_nombre,
            ot.tecnico_id,
            loc.nombre AS ubicacion_nombre,
            (SELECT string_agg(a.nombre, ', ') FROM mantenimiento_ordentrabajo_activos oa
             JOIN activos_activo a ON a.id = oa.activo_id
             WHERE oa.ordentrabajo_id = ot.id) AS activo_nombres
        FROM mantenimiento_ordentrabajo ot
        LEFT JOIN mantenimiento_rutina r ON r.id = ot.rutina_id
        LEFT JOIN auth_user u ON u.id = ot.tecnico_id
        LEFT JOIN activos_ubicacion loc ON loc.id = ot.ubicacion_id
        WHERE ot.inicio_programado >= NOW() - $1::interval
        ORDER BY ot.inicio_programado
        "#,
    )
    .bind(format!("{} days", days_back))
    .fetch_all(pool)
    .await?;

    let orders = rows.iter().map(|row| {
        WorkOrderWithDetails {
            id: row.get("id"),
            codigo_de_orden: row.get("codigo_de_orden"),
            tipo: row.get("tipo"),
            estado: row.get("estado"),
            prioridad: row.get("prioridad"),
            inicio_programado: row.get("inicio_programado"),
            fin_programado: row.get("fin_programado"),
            rutina_nombre: row.get("rutina_nombre"),
            programacion_id: row.get("programacion_id"),
            tecnico_nombre: row.get("tecnico_nombre"),
            tecnico_id: row.get("tecnico_id"),
            ubicacion_nombre: row.get("ubicacion_nombre"),
            activo_nombres: row.get("activo_nombres"),
        }
    }).collect();

    Ok(orders)
}

pub async fn fetch_schedules(pool: &PgPool) -> Result<Vec<Schedule>, sqlx::Error> {
    let rows = sqlx::query(
        r#"SELECT id, nombre, color FROM mantenimiento_horario"#,
    )
    .fetch_all(pool)
    .await?;

    let schedules = rows.iter().map(|row| {
        Schedule {
            id: row.get("id"),
            nombre: row.get("nombre"),
            color: row.get("color"),
        }
    }).collect();

    Ok(schedules)
}

pub async fn fetch_day_schedules(pool: &PgPool) -> Result<Vec<DaySchedule>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT horario_id, dia, hora_inicio, hora_fin
        FROM mantenimiento_diahorario
        ORDER BY horario_id, dia
        "#,
    )
    .fetch_all(pool)
    .await?;

    let ds = rows.iter().map(|row| {
        DaySchedule {
            horario_id: row.get("horario_id"),
            dia: row.get("dia"),
            hora_inicio: row.get("hora_inicio"),
            hora_fin: row.get("hora_fin"),
        }
    }).collect();

    Ok(ds)
}

pub async fn fetch_calendar_restrictions(pool: &PgPool) -> Result<Vec<CalendarRestriction>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT fecha, motivo
        FROM mantenimiento_restriccioncalendario
        WHERE fecha >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY fecha
        "#,
    )
    .fetch_all(pool)
    .await?;

    let res = rows.iter().map(|row| {
        CalendarRestriction {
            fecha: row.get("fecha"),
            motivo: row.get("motivo"),
        }
    }).collect();

    Ok(res)
}

pub async fn fetch_frequencies(pool: &PgPool) -> Result<Vec<Frequency>, sqlx::Error> {
    let rows = sqlx::query(
        r#"SELECT id, nombre, dias FROM mantenimiento_frecuencia"#,
    )
    .fetch_all(pool)
    .await?;

    let freqs = rows.iter().map(|row| {
        Frequency {
            id: row.get("id"),
            nombre: row.get("nombre"),
            dias: row.get("dias"),
        }
    }).collect();

    Ok(freqs)
}

pub async fn fetch_routines(pool: &PgPool) -> Result<Vec<Routine>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT id, nombre, frecuencia_id, cantidad_tecnicos
        FROM mantenimiento_rutina
        "#,
    )
    .fetch_all(pool)
    .await?;

    let routines = rows.iter().map(|row| {
        Routine {
            id: row.get("id"),
            nombre: row.get("nombre"),
            frecuencia_id: row.get("frecuencia_id"),
            cantidad_tecnicos: row.get("cantidad_tecnicos"),
        }
    }).collect();

    Ok(routines)
}

pub async fn fetch_raw_work_orders(pool: &PgPool, days_back: i64) -> Result<Vec<WorkOrder>, sqlx::Error> {
    let rows = sqlx::query(
        r#"
        SELECT
            id, codigo_de_orden, tipo, estado, prioridad,
            inicio_programado, fin_programado,
            rutina_id, programacion_id, tecnico_id, ubicacion_id,
            fecha_ejecucion
        FROM mantenimiento_ordentrabajo
        WHERE inicio_programado >= NOW() - $1::interval
        ORDER BY inicio_programado
        "#,
    )
    .bind(format!("{} days", days_back))
    .fetch_all(pool)
    .await?;

    let orders = rows.iter().map(|row| {
        WorkOrder {
            id: row.get("id"),
            codigo_de_orden: row.get("codigo_de_orden"),
            tipo: row.get("tipo"),
            estado: row.get("estado"),
            prioridad: row.get("prioridad"),
            inicio_programado: row.get("inicio_programado"),
            fin_programado: row.get("fin_programado"),
            rutina_id: row.get("rutina_id"),
            programacion_id: row.get("programacion_id"),
            tecnico_id: row.get("tecnico_id"),
            ubicacion_id: row.get("ubicacion_id"),
            fecha_ejecucion: row.get("fecha_ejecucion"),
        }
    }).collect();

    Ok(orders)
}
