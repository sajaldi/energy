"""
Tareas Celery para exportación asíncrona de riesgos.

Incluye:
- export_riesgos_excel_task: genera XLSX para >100 registros
- export_matriz_pdf_task: genera PDF con mapa de calor y resumen ejecutivo
- cleanup_export_files_task: limpia archivos de exportación con más de 72h

Timeout: 300 segundos (soft_time_limit).
Fallback síncrono si Celery no está disponible (CELERY_TASK_ALWAYS_EAGER).

Requirements: 10.1, 10.2, 10.3, 10.5, 10.6
"""

import os
import json
import logging
from datetime import datetime, timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Directorio base para exportaciones de riesgos
EXPORTS_DIR = os.path.join(settings.MEDIA_ROOT, 'exports', 'riesgos')


def _ensure_exports_dir():
    """Crea el directorio de exportaciones si no existe."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def _generate_filename(prefix, extension):
    """Genera un nombre de archivo con timestamp para unicidad."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{prefix}_{timestamp}.{extension}"


def _save_export_metadata(filepath, user_id, export_type, servicio_id=None):
    """
    Almacena metadata de la exportación en un archivo JSON junto al archivo exportado.
    Incluye: path, user_id, timestamp, tipo, fecha de expiración (72h).
    """
    metadata = {
        'filepath': filepath,
        'user_id': user_id,
        'export_type': export_type,
        'servicio_id': servicio_id,
        'created_at': timezone.now().isoformat(),
        'expires_at': (timezone.now() + timedelta(hours=72)).isoformat(),
    }
    metadata_path = filepath + '.meta.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return metadata_path


def _notify_user_error(user_id, export_type, error_message):
    """
    Registra la notificación de error para el usuario.
    Usa el sistema de logging como fallback si no hay un sistema de notificaciones.
    """
    logger.error(
        f"Exportación {export_type} fallida para usuario {user_id}: {error_message}"
    )
    # Intentar usar el sistema de cache para notificaciones accesibles al usuario
    try:
        from django.core.cache import cache
        cache_key = f"export_error_{export_type}_{user_id}"
        cache.set(cache_key, {
            'status': 'error',
            'message': error_message,
            'timestamp': timezone.now().isoformat(),
        }, timeout=86400)  # 24 horas
    except Exception as e:
        logger.warning(f"No se pudo guardar notificación en cache: {e}")


def _notify_user_success(user_id, export_type, filepath):
    """
    Registra la notificación de éxito para el usuario.
    El archivo estará disponible para descarga durante 72 horas.
    """
    logger.info(
        f"Exportación {export_type} completada para usuario {user_id}: {filepath}"
    )
    try:
        from django.core.cache import cache
        # Ruta relativa al MEDIA_ROOT para construir URL de descarga
        relative_path = os.path.relpath(filepath, settings.MEDIA_ROOT)
        cache_key = f"export_success_{export_type}_{user_id}"
        cache.set(cache_key, {
            'status': 'completed',
            'filepath': relative_path,
            'filename': os.path.basename(filepath),
            'timestamp': timezone.now().isoformat(),
            'expires_at': (timezone.now() + timedelta(hours=72)).isoformat(),
        }, timeout=259200)  # 72 horas
    except Exception as e:
        logger.warning(f"No se pudo guardar notificación en cache: {e}")


@shared_task(
    bind=True,
    name='servicios.tasks_riesgos.export_riesgos_excel_task',
    soft_time_limit=300,
    time_limit=330,
    acks_late=True,
    max_retries=1,
)
def export_riesgos_excel_task(self, servicio_id=None, estado_filter=None, user_id=None):
    """
    Genera un archivo XLSX con el registro de riesgos usando RiesgoResource.

    Se ejecuta de forma asíncrona cuando hay >100 registros.
    El archivo generado estará disponible durante 72 horas.

    Args:
        servicio_id: ID del Servicio para filtrar riesgos (None = todos).
        estado_filter: Filtro de estado ('ACTIVO', 'CERRADO', None = ambos).
        user_id: ID del usuario que solicitó la exportación.

    Returns:
        dict con status, filepath y metadata de la exportación.

    Requirements: 10.1, 10.4, 10.5, 10.6
    """
    try:
        from .models_riesgos import Riesgo
        from .resources_riesgos import RiesgoResource

        _ensure_exports_dir()

        # Construir queryset con filtros
        queryset = Riesgo.objects.select_related(
            'servicio', 'responsable'
        ).prefetch_related(
            'evaluaciones', 'revisiones', 'plan_tratamiento'
        )

        if servicio_id:
            queryset = queryset.filter(servicio_id=servicio_id)

        if estado_filter:
            queryset = queryset.filter(estado=estado_filter)

        # Ordenar por nivel de riesgo descendente (por fecha_identificacion como fallback)
        queryset = queryset.order_by('-fecha_identificacion')

        # Generar exportación con RiesgoResource
        resource = RiesgoResource()
        dataset = resource.export(queryset=queryset)

        # Guardar archivo XLSX
        filename = _generate_filename('riesgos_export', 'xlsx')
        filepath = os.path.join(EXPORTS_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(dataset.xlsx)

        # Guardar metadata
        _save_export_metadata(
            filepath=filepath,
            user_id=user_id,
            export_type='excel',
            servicio_id=servicio_id,
        )

        # Notificar al usuario
        _notify_user_success(user_id, 'excel', filepath)

        logger.info(
            f"Exportación Excel completada: {filename} "
            f"({queryset.count()} registros)"
        )

        return {
            'status': 'completed',
            'filepath': filepath,
            'filename': filename,
            'records': queryset.count(),
        }

    except SoftTimeLimitExceeded:
        error_msg = (
            "La exportación Excel no pudo completarse en el tiempo límite "
            "de 300 segundos. Intente con un filtro más específico."
        )
        _notify_user_error(user_id, 'excel', error_msg)
        logger.error(f"Timeout en export_riesgos_excel_task: {error_msg}")
        return {
            'status': 'error',
            'message': error_msg,
        }

    except Exception as exc:
        error_msg = (
            "La exportación no pudo completarse debido a un error de procesamiento. "
            "Puede reintentar la operación."
        )
        _notify_user_error(user_id, 'excel', error_msg)
        logger.exception(f"Error en export_riesgos_excel_task: {exc}")
        return {
            'status': 'error',
            'message': error_msg,
            'detail': str(exc),
        }


@shared_task(
    bind=True,
    name='servicios.tasks_riesgos.export_matriz_pdf_task',
    soft_time_limit=300,
    time_limit=330,
    acks_late=True,
    max_retries=1,
)
def export_matriz_pdf_task(self, servicio_id, user_id=None):
    """
    Genera un PDF con el mapa de calor y resumen ejecutivo de la matriz de riesgos.

    El PDF incluye:
    - Mapa de calor 5×5 (renderizado HTML→PDF)
    - Tabla de riesgos con código, título, zona y responsable
    - Resumen ejecutivo: total por zona, % planes completados,
      revisiones vencidas, fecha de generación

    Args:
        servicio_id: ID del Servicio (obligatorio para PDF de matriz).
        user_id: ID del usuario que solicitó la exportación.

    Returns:
        dict con status, filepath y metadata de la exportación.

    Requirements: 10.2, 10.3, 10.5, 10.6
    """
    try:
        from .models_riesgos import Riesgo, EvaluacionRiesgo, PlanTratamiento
        from .models import Servicio

        _ensure_exports_dir()

        servicio = Servicio.objects.get(pk=servicio_id)

        # Obtener riesgos activos del servicio
        riesgos = Riesgo.objects.filter(
            servicio=servicio,
            estado='ACTIVO'
        ).select_related('responsable').prefetch_related('evaluaciones')

        # Calcular resumen ejecutivo
        total_riesgos = riesgos.count()
        resumen_zonas = {
            'BAJO': 0,
            'MEDIO': 0,
            'ALTO': 0,
            'CRITICO': 0,
        }

        # Tabla de riesgos para el PDF
        tabla_riesgos = []
        for riesgo in riesgos:
            eval_residual = (
                riesgo.evaluaciones
                .filter(tipo='RESIDUAL')
                .order_by('-fecha_evaluacion')
                .first()
            )
            zona = eval_residual.zona_riesgo if eval_residual else 'SIN_EVALUAR'
            if zona in resumen_zonas:
                resumen_zonas[zona] += 1

            tabla_riesgos.append({
                'codigo': riesgo.codigo,
                'titulo': riesgo.titulo,
                'zona_riesgo': zona,
                'responsable': (
                    riesgo.responsable.get_full_name() or riesgo.responsable.username
                ) if riesgo.responsable else 'Sin asignar',
            })

        # Porcentaje de planes implementados
        total_planes = PlanTratamiento.objects.filter(
            riesgo__servicio=servicio
        ).count()
        planes_implementados = PlanTratamiento.objects.filter(
            riesgo__servicio=servicio,
            estado='IMPLEMENTADO'
        ).count()
        pct_implementados = (
            round((planes_implementados / total_planes) * 100, 1)
            if total_planes > 0 else 0
        )

        # Revisiones vencidas
        revisiones_vencidas = riesgos.filter(estado_revision='VENCIDA').count()

        resumen_ejecutivo = {
            'servicio': servicio.nombre,
            'total_riesgos': total_riesgos,
            'zonas': resumen_zonas,
            'pct_planes_implementados': pct_implementados,
            'revisiones_vencidas': revisiones_vencidas,
            'fecha_generacion': timezone.now().strftime('%Y-%m-%d %H:%M'),
        }

        # Generar PDF con template HTML
        filename = _generate_filename(f'matriz_{servicio.codigo or servicio.pk}', 'pdf')
        filepath = os.path.join(EXPORTS_DIR, filename)

        pdf_generated = _render_pdf(
            filepath=filepath,
            servicio=servicio,
            tabla_riesgos=tabla_riesgos,
            resumen_ejecutivo=resumen_ejecutivo,
        )

        if not pdf_generated:
            # Fallback: generar un resumen en texto si no hay motor PDF disponible
            filepath = filepath.replace('.pdf', '.txt')
            filename = filename.replace('.pdf', '.txt')
            _generate_text_report(filepath, resumen_ejecutivo, tabla_riesgos)

        # Guardar metadata
        _save_export_metadata(
            filepath=filepath,
            user_id=user_id,
            export_type='pdf',
            servicio_id=servicio_id,
        )

        # Notificar al usuario
        _notify_user_success(user_id, 'pdf', filepath)

        logger.info(
            f"Exportación PDF completada: {filename} "
            f"(Servicio: {servicio.nombre}, {total_riesgos} riesgos)"
        )

        return {
            'status': 'completed',
            'filepath': filepath,
            'filename': filename,
            'servicio': servicio.nombre,
            'total_riesgos': total_riesgos,
        }

    except SoftTimeLimitExceeded:
        error_msg = (
            "La exportación PDF no pudo completarse en el tiempo límite "
            "de 300 segundos. Intente con un servicio con menos riesgos."
        )
        _notify_user_error(user_id, 'pdf', error_msg)
        logger.error(f"Timeout en export_matriz_pdf_task: {error_msg}")
        return {
            'status': 'error',
            'message': error_msg,
        }

    except Exception as exc:
        error_msg = (
            "La exportación PDF no pudo completarse debido a un error de procesamiento. "
            "Puede reintentar la operación."
        )
        _notify_user_error(user_id, 'pdf', error_msg)
        logger.exception(f"Error en export_matriz_pdf_task: {exc}")
        return {
            'status': 'error',
            'message': error_msg,
            'detail': str(exc),
        }


def _render_pdf(filepath, servicio, tabla_riesgos, resumen_ejecutivo):
    """
    Intenta renderizar el PDF usando weasyprint.
    Retorna True si se generó correctamente, False si weasyprint no está disponible.
    """
    try:
        from django.template.loader import render_to_string
        import weasyprint

        html_content = render_to_string(
            'servicios/riesgos/export_pdf.html',
            {
                'servicio': servicio,
                'tabla_riesgos': tabla_riesgos,
                'resumen': resumen_ejecutivo,
            }
        )

        doc = weasyprint.HTML(string=html_content)
        doc.write_pdf(filepath)
        return True

    except ImportError:
        logger.warning(
            "weasyprint no está instalado. "
            "Se generará un reporte de texto como fallback."
        )
        return False
    except Exception as e:
        logger.error(f"Error al renderizar PDF con weasyprint: {e}")
        return False


def _generate_text_report(filepath, resumen_ejecutivo, tabla_riesgos):
    """
    Genera un reporte de texto plano como fallback cuando weasyprint no está disponible.
    """
    lines = [
        "=" * 70,
        f"MATRIZ DE RIESGOS - {resumen_ejecutivo['servicio']}",
        "=" * 70,
        f"Fecha de generación: {resumen_ejecutivo['fecha_generacion']}",
        "",
        "RESUMEN EJECUTIVO",
        "-" * 40,
        f"Total de riesgos activos: {resumen_ejecutivo['total_riesgos']}",
        f"  - Bajo: {resumen_ejecutivo['zonas']['BAJO']}",
        f"  - Medio: {resumen_ejecutivo['zonas']['MEDIO']}",
        f"  - Alto: {resumen_ejecutivo['zonas']['ALTO']}",
        f"  - Crítico: {resumen_ejecutivo['zonas']['CRITICO']}",
        f"Planes de tratamiento implementados: {resumen_ejecutivo['pct_planes_implementados']}%",
        f"Revisiones vencidas: {resumen_ejecutivo['revisiones_vencidas']}",
        "",
        "LISTADO DE RIESGOS",
        "-" * 40,
        f"{'Código':<15} {'Zona':<12} {'Responsable':<20} {'Título'}",
        "-" * 70,
    ]

    for riesgo in tabla_riesgos:
        lines.append(
            f"{riesgo['codigo']:<15} {riesgo['zona_riesgo']:<12} "
            f"{riesgo['responsable']:<20} {riesgo['titulo'][:30]}"
        )

    lines.append("")
    lines.append("=" * 70)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


@shared_task(
    name='servicios.tasks_riesgos.cleanup_export_files_task',
    soft_time_limit=60,
)
def cleanup_export_files_task():
    """
    Elimina archivos de exportación con más de 72 horas de antigüedad.

    Se ejecuta periódicamente via Celery Beat para mantener el directorio
    de exportaciones limpio. Elimina tanto los archivos de exportación como
    sus archivos de metadata asociados (.meta.json).

    Requirements: 10.5 (archivos disponibles 72h)
    """
    if not os.path.exists(EXPORTS_DIR):
        return {'status': 'ok', 'message': 'No exports directory found', 'deleted': 0}

    cutoff_time = timezone.now() - timedelta(hours=72)
    deleted_count = 0
    errors = []

    for filename in os.listdir(EXPORTS_DIR):
        filepath = os.path.join(EXPORTS_DIR, filename)

        if not os.path.isfile(filepath):
            continue

        try:
            # Verificar antigüedad del archivo
            file_mtime = datetime.fromtimestamp(
                os.path.getmtime(filepath),
                tz=timezone.get_current_timezone()
            )

            if file_mtime < cutoff_time:
                os.remove(filepath)
                deleted_count += 1
                logger.info(f"Archivo de exportación eliminado: {filename}")
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
            logger.warning(f"Error al eliminar {filename}: {e}")

    result = {
        'status': 'completed',
        'deleted': deleted_count,
        'errors': errors,
    }
    logger.info(f"Cleanup de exportaciones completado: {deleted_count} archivos eliminados.")
    return result


# =============================================================================
# Tareas de Notificación Periódica (task 14.2)
# Requirements: 4.7, 5.2, 5.3, 5.6, 5.7
# =============================================================================


@shared_task(
    bind=True,
    name='servicios.tasks_riesgos.check_review_notifications',
    max_retries=3,
    soft_time_limit=120,
)
def check_review_notifications(self):
    """
    Tarea diaria que verifica el estado de revisión de todos los riesgos activos:

    1. Riesgos con revisión a 7 días: notifica "Revisión próxima" al responsable.
    2. Riesgos con revisión vencida (fecha cumplida): marca estado_revision='VENCIDA'
       y notifica "Revisión requerida" al responsable.
    3. Riesgos con revisión vencida >15 días: escalamiento al responsable del Servicio.

    Registra las notificaciones en RiesgoHistorial.
    Requirements: 5.2, 5.3, 5.6, 5.7.
    """
    from datetime import date, timedelta as td
    from .models_riesgos import Riesgo, RiesgoHistorial

    try:
        today = date.today()
        quince_dias_atras = today - td(days=15)

        # Obtener todos los riesgos activos con próxima revisión programada
        riesgos_activos = Riesgo.objects.filter(
            estado='ACTIVO',
            proxima_revision__isnull=False,
        ).select_related('servicio', 'responsable')

        notificaciones_proxima = 0
        notificaciones_vencida = 0
        escalamientos = 0

        for riesgo in riesgos_activos:
            dias_restantes = (riesgo.proxima_revision - today).days

            if dias_restantes <= 0:
                # ----- REVISIÓN VENCIDA -----
                # Actualizar estado de revisión a VENCIDA
                riesgo.actualizar_estado_revision()

                # Notificar al responsable: "Revisión requerida"
                RiesgoHistorial.objects.create(
                    riesgo=riesgo,
                    tipo_evento='REVISION',
                    valores_nuevos={
                        'notificacion': 'Revisión requerida',
                        'proxima_revision': str(riesgo.proxima_revision),
                        'dias_vencida': abs(dias_restantes),
                        'responsable': (
                            riesgo.responsable.get_full_name()
                            if riesgo.responsable else 'Sin asignar'
                        ),
                    },
                    usuario=riesgo.responsable,
                )
                notificaciones_vencida += 1

                logger.info(
                    f"Revisión vencida: Riesgo {riesgo.codigo}, "
                    f"{abs(dias_restantes)} días de atraso. "
                    f"Responsable: {riesgo.responsable}"
                )

                # Escalamiento si revisión vencida >15 días
                if riesgo.proxima_revision <= quince_dias_atras:
                    dias_atraso = abs(dias_restantes)
                    responsable_servicio = _obtener_responsable_servicio(riesgo.servicio)

                    RiesgoHistorial.objects.create(
                        riesgo=riesgo,
                        tipo_evento='REVISION',
                        valores_nuevos={
                            'notificacion': 'Escalamiento por revisión vencida >15 días',
                            'codigo_riesgo': riesgo.codigo,
                            'responsable_riesgo': (
                                riesgo.responsable.get_full_name()
                                if riesgo.responsable else 'Sin asignar'
                            ),
                            'dias_atraso': dias_atraso,
                            'escalado_a': (
                                responsable_servicio.get_full_name()
                                if responsable_servicio else 'Sin responsable de servicio'
                            ),
                        },
                        usuario=responsable_servicio,
                    )
                    escalamientos += 1

                    logger.warning(
                        f"ESCALAMIENTO: Riesgo {riesgo.codigo} con revisión vencida "
                        f"{dias_atraso} días. Escalado a responsable de servicio "
                        f"'{riesgo.servicio.nombre}'."
                    )

            elif dias_restantes <= 7:
                # ----- REVISIÓN PRÓXIMA (dentro de 7 días) -----
                # Actualizar estado de revisión
                riesgo.actualizar_estado_revision()

                # Notificar al responsable: "Revisión próxima"
                RiesgoHistorial.objects.create(
                    riesgo=riesgo,
                    tipo_evento='REVISION',
                    valores_nuevos={
                        'notificacion': 'Revisión próxima',
                        'proxima_revision': str(riesgo.proxima_revision),
                        'dias_restantes': dias_restantes,
                        'responsable': (
                            riesgo.responsable.get_full_name()
                            if riesgo.responsable else 'Sin asignar'
                        ),
                    },
                    usuario=riesgo.responsable,
                )
                notificaciones_proxima += 1

            else:
                # Más de 7 días restantes: solo actualizar estado por si acaso
                riesgo.actualizar_estado_revision()

        logger.info(
            f"check_review_notifications completada: "
            f"{notificaciones_proxima} próximas, "
            f"{notificaciones_vencida} vencidas, "
            f"{escalamientos} escalamientos."
        )

        return {
            'status': 'success',
            'notificaciones_proxima': notificaciones_proxima,
            'notificaciones_vencida': notificaciones_vencida,
            'escalamientos': escalamientos,
        }

    except Exception as exc:
        logger.error(f"Error en check_review_notifications: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(
    bind=True,
    name='servicios.tasks_riesgos.check_overdue_actions',
    max_retries=3,
    soft_time_limit=120,
)
def check_overdue_actions(self):
    """
    Tarea diaria que verifica acciones de planes de tratamiento con fecha
    límite vencida y estado PENDIENTE o EN_PROGRESO.

    Para cada acción vencida:
    - Crea notificación para el responsable de la acción.
    - Registra en RiesgoHistorial del riesgo asociado.

    Requirements: 4.7.
    """
    from datetime import date
    from .models_riesgos import AccionTratamiento, RiesgoHistorial

    try:
        today = date.today()

        # Acciones con fecha límite vencida y estado pendiente o en progreso
        acciones_vencidas = AccionTratamiento.objects.filter(
            fecha_limite__lt=today,
            estado__in=['PENDIENTE', 'EN_PROGRESO'],
        ).select_related('plan__riesgo', 'responsable')

        notificaciones = 0

        for accion in acciones_vencidas:
            riesgo = accion.plan.riesgo
            dias_vencida = (today - accion.fecha_limite).days

            # Registrar notificación en historial del riesgo
            RiesgoHistorial.objects.create(
                riesgo=riesgo,
                tipo_evento='TRATAMIENTO',
                valores_nuevos={
                    'notificacion': 'Acción de tratamiento vencida',
                    'accion_id': accion.pk,
                    'descripcion': accion.descripcion[:100],
                    'fecha_limite': str(accion.fecha_limite),
                    'dias_vencida': dias_vencida,
                    'estado': accion.estado,
                    'responsable': (
                        accion.responsable.get_full_name()
                        if accion.responsable else 'Sin asignar'
                    ),
                },
                usuario=accion.responsable,
            )
            notificaciones += 1

            logger.info(
                f"Acción vencida: Riesgo {riesgo.codigo}, "
                f"acción '{accion.descripcion[:50]}', "
                f"{dias_vencida} días de atraso. "
                f"Responsable: {accion.responsable}"
            )

        logger.info(
            f"check_overdue_actions completada: "
            f"{notificaciones} notificaciones de acciones vencidas."
        )

        return {
            'status': 'success',
            'acciones_vencidas': notificaciones,
        }

    except Exception as exc:
        logger.error(f"Error en check_overdue_actions: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


# =============================================================================
# Utilidades para notificaciones
# =============================================================================

def _obtener_responsable_servicio(servicio):
    """
    Obtiene el responsable del Servicio para escalamiento de notificaciones.
    Busca en orden:
    1. Campo 'responsable' del modelo Servicio (si existe).
    2. Primer superusuario activo como fallback.
    3. None si no hay ninguno disponible.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Intentar obtener responsable del servicio (si el modelo tiene ese campo)
    responsable = getattr(servicio, 'responsable', None)
    if responsable:
        return responsable

    # Buscar el primer superusuario activo como fallback
    superuser = User.objects.filter(is_superuser=True, is_active=True).first()
    if superuser:
        return superuser

    return None
