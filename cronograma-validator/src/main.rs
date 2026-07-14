mod db;
mod models;
mod validator;
mod report;

use clap::Parser;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "cronograma-validator")]
#[command(about = "Verifica la consistencia del cronograma de órdenes de trabajo")]
struct Cli {
    /// URL de conexión PostgreSQL
    #[arg(short, long, env = "DATABASE_URL")]
    database_url: String,

    /// Días hacia atrás para analizar (default: 365)
    #[arg(short, long, default_value_t = 365)]
    days: i64,

    /// Ruta de salida para reporte HTML (opcional)
    #[arg(short, long)]
    output: Option<PathBuf>,

    /// Solo salida JSON
    #[arg(long)]
    json: bool,
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    println!("🔌 Conectando a PostgreSQL...");
    let pool = match db::connect(&cli.database_url).await {
        Ok(p) => p,
        Err(e) => {
            eprintln!("❌ Error de conexión: {}", e);
            std::process::exit(1);
        }
    };
    println!("✅ Conectado exitosamente\n");

    println!("📦 Cargando datos (últimos {} días)...", cli.days);

    let (orders, raw_orders, schedules, day_schedules, restrictions, frequencies, routines) = tokio::join!(
        db::fetch_work_orders(&pool, cli.days),
        db::fetch_raw_work_orders(&pool, cli.days),
        db::fetch_schedules(&pool),
        db::fetch_day_schedules(&pool),
        db::fetch_calendar_restrictions(&pool),
        db::fetch_frequencies(&pool),
        db::fetch_routines(&pool),
    );

    let orders = orders.unwrap_or_else(|e| { eprintln!("⚠️ Error cargando órdenes: {}", e); vec![] });
    let raw_orders = raw_orders.unwrap_or_else(|e| { eprintln!("⚠️ Error cargando órdenes crudas: {}", e); vec![] });
    let schedules = schedules.unwrap_or_else(|e| { eprintln!("⚠️ Error cargando horarios: {}", e); vec![] });
    let day_schedules = day_schedules.unwrap_or_else(|e| { eprintln!("⚠️ Error cargando días: {}", e); vec![] });
    let restrictions = restrictions.unwrap_or_else(|e| { eprintln!("⚠️ Error cargando restricciones: {}", e); vec![] });
    let frequencies = frequencies.unwrap_or_else(|e| { eprintln!("⚠️ Error cargando frecuencias: {}", e); vec![] });
    let routines = routines.unwrap_or_else(|e| { eprintln!("⚠️ Error cargando rutinas: {}", e); vec![] });

    println!(
        "   {} órdenes, {} horarios, {} restricciones, {} frecuencias, {} rutinas\n",
        orders.len(),
        schedules.len(),
        restrictions.len(),
        frequencies.len(),
        routines.len(),
    );

    println!("🔍 Ejecutando validaciones...");
    let issues = validator::Validator::validate_all(
        &orders,
        &raw_orders,
        &schedules,
        &day_schedules,
        &restrictions,
        &frequencies,
        &routines,
    );
    let summary = validator::Validator::compute_summary(&issues, &orders);

    if cli.json {
        let output = serde_json::json!({
            "summary": summary,
            "issues": issues,
        });
        println!("{}", serde_json::to_string_pretty(&output).unwrap());
        return;
    }

    report::print_cli_report(&issues, &summary);

    if let Some(path) = cli.output {
        match report::generate_html_report(&issues, &summary) {
            Ok(html) => {
                std::fs::write(&path, &html).unwrap_or_else(|e| {
                    eprintln!("⚠️ Error escribiendo reporte HTML: {}", e);
                });
                println!("📄 Reporte HTML generado: {}", path.display());
            }
            Err(e) => {
                eprintln!("⚠️ Error generando reporte HTML: {}", e);
            }
        }
    }
}
