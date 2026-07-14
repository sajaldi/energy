use colored::*;
use tera::{Tera, Context};
use crate::models::*;

pub fn print_cli_report(issues: &[ValidationIssue], summary: &ValidationSummary) {
    println!();
    println!("═══════════════════════════════════════════════");
    println!("  CRONOGRAMA VALIDATOR - REPORTE DE VERIFICACIÓN");
    println!("═══════════════════════════════════════════════");
    println!();

    println!("  {} órdenes de trabajo revisadas", summary.total_orders.to_string().bold());
    println!("  {} problemas encontrados:", summary.total_issues.to_string().bold());
    println!(
        "    {}  {} errores",
        "●".red(),
        summary.errors.to_string().red().bold()
    );
    println!(
        "    {}  {} advertencias",
        "●".yellow(),
        summary.warnings.to_string().yellow().bold()
    );
    println!(
        "    {}  {} info",
        "●".cyan(),
        summary.info.to_string().cyan().bold()
    );

    if !summary.by_category.is_empty() {
        println!();
        println!("┌────── Por Categoría ──────────────────────┐");
        for cc in &summary.by_category {
            println!("  {}: {}", cc.category, cc.count.to_string().bold());
        }
        println!("└─────────────────────────────────────────────┘");
    }

    if !issues.is_empty() {
        println!();
        println!("┌────── Detalle de Problemas ────────────────┐");
        for issue in issues {
            let icon = match issue.severity {
                Severity::Error => "✖",
                Severity::Warning => "⚠",
                Severity::Info => "ℹ",
            };
            let color = match issue.severity {
                Severity::Error => Color::Red,
                Severity::Warning => Color::Yellow,
                Severity::Info => Color::Cyan,
            };
            println!(
                "  {} [{}] {}",
                icon.color(color).bold(),
                issue.severity.to_string().color(color),
                issue.message.bold(),
            );
            if let Some(ref codigo) = issue.codigo {
                println!("     OT: {}", codigo);
            }
            println!("     {}", issue.detail);
            println!();
        }
        println!("└─────────────────────────────────────────────┘");
    }

    println!();
    println!("{}", "✓ Validación completada".green().bold());
}

pub fn generate_html_report(
    issues: &[ValidationIssue],
    summary: &ValidationSummary,
) -> Result<String, tera::Error> {
    let template_str = include_str!("../templates/report.html");

    let mut tera = Tera::default();
    tera.add_raw_template("report", template_str)?;

    let mut ctx = Context::new();
    ctx.insert("summary", summary);
    ctx.insert("issues", issues);

    tera.render("report", &ctx)
}
