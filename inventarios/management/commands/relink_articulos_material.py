from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.db import transaction

from inventarios.models import Material
from presupuestos.models import ArticuloRequisicion
from inventarios.api_materials import (
    _normalizar_texto,
    _tokens_significativos,
    _material_es_placeholder,
)


def _score_coincidencia(descripcion, material):
    """Devuelve un puntaje de 0 a 1 de qué tanto corresponde el artículo al material."""
    desc_norm = _normalizar_texto(descripcion)
    if not desc_norm:
        return 0.0

    sku_norm = _normalizar_texto(material.sku)
    if sku_norm and sku_norm in desc_norm:
        return 1.0

    nombre_norm = _normalizar_texto(material.nombre)
    if nombre_norm and nombre_norm in desc_norm:
        return 1.0

    tokens_material = _tokens_significativos(nombre_norm)
    if not tokens_material:
        return 0.0
    tokens_desc = _tokens_significativos(desc_norm)
    coinciden = tokens_material & tokens_desc
    return len(coinciden) / len(tokens_material)


class Command(BaseCommand):
    help = (
        "Re-vincula artículos de requisición huérfanos (material NULL o vinculado a "
        "un material placeholder) a su material real del catálogo, según coincidencia "
        "por SKU/nombre. Usa --commit para aplicar; por defecto solo muestra el reporte."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Aplica los cambios en la base de datos (por defecto solo reporta).',
        )
        parser.add_argument(
            '--commit-umbral',
            type=float,
            default=0.85,
            help='Puntaje mínimo de coincidencia para re-vincular automáticamente (0-1).',
        )
        parser.add_argument(
            '--review-umbral',
            type=float,
            default=0.5,
            help='Puntaje mínimo para listar como candidato a revisión manual (0-1).',
        )
        parser.add_argument(
            '--material',
            type=int,
            default=None,
            help='Limitar el proceso a un material específico (id).',
        )

    def handle(self, *args, **options):
        commit = options['commit']
        commit_umbral = options['commit_umbral']
        review_umbral = options['review_umbral']
        material_id = options['material']

        if not 0 <= commit_umbral <= 1 or not 0 <= review_umbral <= 1:
            raise CommandError('Los umbrales deben estar entre 0 y 1.')
        if commit_umbral < review_umbral:
            raise CommandError('--commit-umbral debe ser >= --review-umbral.')

        ids_placeholder = [
            m.id for m in Material.objects.filter(
                Q(nombre__icontains='fuera de cat') | Q(nombre__icontains='sin cat')
            ) if _material_es_placeholder(m)
        ]

        huérfanos = ArticuloRequisicion.objects.filter(
            Q(material__isnull=True) | Q(material_id__in=ids_placeholder)
        ).select_related('material', 'requisicion')

        materiales = list(Material.objects.all().exclude(pk__in=ids_placeholder))

        propuestas = []   # (articulo, material_candidato, score, motivo) -> auto-vincular
        revisar = []      # (articulo, material_candidato, score) -> revisión manual
        ambiguos = []     # (articulo, [ (material, score) ])

        for art in huérfanos:
            desc = art.cr8ca_articulo or ''
            if not desc:
                continue

            mejores = []
            for mat in materiales:
                if material_id and mat.pk != material_id:
                    continue
                score = _score_coincidencia(desc, mat)
                if score >= review_umbral:
                    mejores.append((mat, score))

            if not mejores:
                continue
            mejores.sort(key=lambda x: x[1], reverse=True)
            mejor, mejor_score = mejores[0]
            # Si hay empate o el segundo candidato es casi igual, marcar ambiguo
            if len(mejores) > 1 and mejor_score - mejores[1][1] < 0.15:
                ambiguos.append((art, mejores))
                continue
            if mejor_score >= commit_umbral:
                propuestas.append((art, mejor, mejor_score, desc))
            else:
                revisar.append((art, mejor, mejor_score, desc))

        propuestas.sort(key=lambda x: x[2], reverse=True)
        revisar.sort(key=lambda x: x[2], reverse=True)
        ambiguos.sort(key=lambda x: -x[0].requisicion.fecha.timestamp() if x[0].requisicion and x[0].requisicion.fecha else 0)

        self.stdout.write(self.style.MIGRATE_HEADING('=== REPORTE DE RE-VINCULACIÓN ==='))
        self.stdout.write('Artículos huérfanos totales: %d' % huérfanos.count())
        self.stdout.write('Auto-vinculación (score >= %.2f): %d' % (commit_umbral, len(propuestas)))
        self.stdout.write('Revisión manual (%.2f <= score < %.2f): %d' % (review_umbral, commit_umbral, len(revisar)))
        self.stdout.write('Ambiguos (empate entre candidatos): %d\n' % len(ambiguos))

        for art, mat, score, desc in propuestas:
            req_num = art.requisicion.cr8ca_requisicion if art.requisicion else '—'
            self.stdout.write(
                '  [OK %.2f] %s | "%s" -> #%s %s (%s)'
                % (score, req_num, (desc or '')[:60], mat.pk, mat.nombre, mat.sku)
            )

        if revisar:
            self.stdout.write(self.style.WARNING('\n--- REVISIÓN MANUAL (no se tocan) ---'))
            for art, mat, score, desc in revisar:
                req_num = art.requisicion.cr8ca_requisicion if art.requisicion else '—'
                self.stdout.write(
                    '  ~ %.2f %s | "%s" -> #%s %s (%s)'
                    % (score, req_num, (desc or '')[:60], mat.pk, mat.nombre, mat.sku)
                )

        if ambiguos:
            self.stdout.write(self.style.WARNING('\n--- AMBIGUOS (no se tocan) ---'))
            for art, mejores in ambiguos:
                req_num = art.requisicion.cr8ca_requisicion if art.requisicion else '—'
                cands = ', '.join('#%s %s (%.2f)' % (m.pk, m.nombre, s) for m, s in mejores)
                self.stdout.write('  ? %s | "%s" -> %s' % (req_num, (art.cr8ca_articulo or '')[:60], cands))

        if not commit:
            self.stdout.write(self.style.WARNING('\nModo reporte (dry-run). Usa --commit para aplicar.'))
            return

        with transaction.atomic():
            aplicados = 0
            for art, mat, score, desc in propuestas:
                art.material = mat
                art.save(update_fields=['material'])
                aplicados += 1
            self.stdout.write(self.style.SUCCESS('\nSe re-vincularon %d artículo(s).' % aplicados))
