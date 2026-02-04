"""
Script de prueba para el sistema de Bien Afecto
Demuestra las nuevas funcionalidades implementadas
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.contrib.auth.models import User
from activos.models import BienAfecto, HistorialBienAfecto, Activo, Familia
from django.utils import timezone
from datetime import timedelta

def test_bien_afecto():
    print("=" * 80)
    print("PRUEBA DEL SISTEMA DE BIEN AFECTO")
    print("=" * 80)
    
    # 1. Obtener o crear usuario de prueba
    usuario, _ = User.objects.get_or_create(
        username='admin',
        defaults={'is_staff': True, 'is_superuser': True}
    )
    print(f"\n✓ Usuario: {usuario.username}")
    
    # 2. Crear o obtener familia
    familia, _ = Familia.objects.get_or_create(
        nombre='Bombas',
        defaults={'descripcion': 'Equipos de bombeo'}
    )
    print(f"✓ Familia: {familia.nombre}")
    
    # 3. Crear Bien Afecto
    bien_afecto, created = BienAfecto.objects.get_or_create(
        codigo_interno='PUMP-TEST-001',
        defaults={
            'nombre': 'Bomba Principal - Prueba',
            'familia': familia,
            'responsable': usuario
        }
    )
    
    if created:
        print(f"\n✓ Bien Afecto creado: {bien_afecto.codigo_interno}")
    else:
        print(f"\n✓ Bien Afecto existente: {bien_afecto.codigo_interno}")
    
    # 4. Crear activos de prueba
    activo1, _ = Activo.objects.get_or_create(
        codigo_interno='ACT-PUMP-001',
        defaults={
            'nombre': 'Bomba Grundfos CR5',
            'serie': 'GF12345',
            'estado': 'OPERATIVO'
        }
    )
    
    activo2, _ = Activo.objects.get_or_create(
        codigo_interno='ACT-PUMP-002',
        defaults={
            'nombre': 'Bomba Grundfos CR10',
            'serie': 'GF67890',
            'estado': 'OPERATIVO'
        }
    )
    
    activo3, _ = Activo.objects.get_or_create(
        codigo_interno='ACT-PUMP-003',
        defaults={
            'nombre': 'Bomba Grundfos CR15',
            'serie': 'GF11223',
            'estado': 'OPERATIVO'
        }
    )
    
    print(f"✓ Activos creados: {activo1.nombre}, {activo2.nombre}, {activo3.nombre}")
    
    # 5. Limpiar historial previo para la prueba
    bien_afecto.historial.all().delete()
    print("\n✓ Historial limpiado para prueba limpia")
    
    # 6. Dar de alta el primer activo
    print("\n" + "=" * 80)
    print("PRUEBA 1: Alta del primer activo")
    print("=" * 80)
    
    historial1 = HistorialBienAfecto(
        bien_afecto=bien_afecto,
        activo=activo1,
        usuario_alta=usuario
    )
    historial1.save(skip_validation=True)
    
    # Simular que fue dado de alta hace 2 años
    HistorialBienAfecto.objects.filter(pk=historial1.pk).update(
        fecha_alta=timezone.now() - timedelta(days=730)
    )
    historial1.refresh_from_db()
    
    print(f"✓ Activo dado de alta: {activo1.nombre}")
    print(f"  - Fecha: {historial1.fecha_alta.strftime('%d/%m/%Y')}")
    print(f"  - Usuario: {historial1.usuario_alta.username}")
    print(f"  - Activo actual del bien afecto: {bien_afecto.activo_actual.nombre}")
    
    # 7. Probar método reemplazar_activo()
    print("\n" + "=" * 80)
    print("PRUEBA 2: Reemplazo de activo (método helper)")
    print("=" * 80)
    
    # Simular que el reemplazo fue hace 1 año
    historial2 = bien_afecto.reemplazar_activo(
        nuevo_activo=activo2,
        motivo_baja='DAÑADO',
        usuario=usuario,
        observaciones='Falla en rodamientos, ruido excesivo'
    )
    
    
    # Ajustar fechas para simular historial
    HistorialBienAfecto.objects.filter(pk=historial1.pk).update(
        fecha_baja=timezone.now() - timedelta(days=365)
    )
    
    HistorialBienAfecto.objects.filter(pk=historial2.pk).update(
        fecha_alta=timezone.now() - timedelta(days=365)
    )
    
    # Refrescar objetos
    historial1.refresh_from_db()
    historial2.refresh_from_db()
    
    print(f"✓ Activo anterior dado de baja: {activo1.nombre}")
    print(f"  - Motivo: {historial1.get_motivo_baja_display()}")
    print(f"  - Observaciones: {historial1.observaciones_baja}")
    print(f"\n✓ Nuevo activo dado de alta: {activo2.nombre}")
    print(f"  - Activo actual del bien afecto: {bien_afecto.activo_actual.nombre}")
    
    # 8. Segundo reemplazo
    print("\n" + "=" * 80)
    print("PRUEBA 3: Segundo reemplazo")
    print("=" * 80)
    
    historial3 = bien_afecto.reemplazar_activo(
        nuevo_activo=activo3,
        motivo_baja='REEMPLAZO',
        usuario=usuario,
        observaciones='Actualización a modelo de mayor capacidad'
    )
    
    print(f"✓ Activo anterior dado de baja: {activo2.nombre}")
    print(f"  - Motivo: {historial2.get_motivo_baja_display()}")
    print(f"\n✓ Nuevo activo dado de alta: {activo3.nombre}")
    print(f"  - Activo actual del bien afecto: {bien_afecto.activo_actual.nombre}")
    
    # 9. Mostrar historial completo
    print("\n" + "=" * 80)
    print("PRUEBA 4: Historial completo")
    print("=" * 80)
    
    for i, registro in enumerate(bien_afecto.historial_completo(), 1):
        print(f"\n{i}. {registro.activo.nombre}")
        print(f"   Alta: {registro.fecha_alta.strftime('%d/%m/%Y %H:%M')} por {registro.usuario_alta.username}")
        if registro.fecha_baja:
            print(f"   Baja: {registro.fecha_baja.strftime('%d/%m/%Y %H:%M')} por {registro.usuario_baja.username}")
            print(f"   Motivo: {registro.get_motivo_baja_display()}")
            print(f"   Observaciones: {registro.observaciones_baja}")
            duracion = (registro.fecha_baja - registro.fecha_alta).days
            print(f"   Duración: {duracion} días")
        else:
            print(f"   Estado: ✓ ACTIVO")
    
    # 10. Calcular vida útil promedio
    print("\n" + "=" * 80)
    print("PRUEBA 5: Análisis de vida útil")
    print("=" * 80)
    
    vida_util = bien_afecto.tiempo_promedio_vida_util()
    if vida_util:
        dias = vida_util.days
        if dias >= 365:
            vida_util_str = f"{dias // 365} años, {(dias % 365) // 30} meses"
        elif dias >= 30:
            vida_util_str = f"{dias // 30} meses, {dias % 30} días"
        else:
            vida_util_str = f"{dias} días"
        
        print(f"✓ Vida útil promedio: {vida_util_str}")
        print(f"  - Total de activos: {bien_afecto.historial.count()}")
        print(f"  - Activos dados de baja: {bien_afecto.historial.filter(fecha_baja__isnull=False).count()}")
    else:
        print("⚠ No hay suficientes datos para calcular vida útil promedio")
    
    # 11. Probar validación (intentar dar de alta otro activo sin dar de baja el actual)
    print("\n" + "=" * 80)
    print("PRUEBA 6: Validación (debe fallar)")
    print("=" * 80)
    
    try:
        activo4, _ = Activo.objects.get_or_create(
            codigo_interno='ACT-PUMP-004',
            defaults={
                'nombre': 'Bomba Grundfos CR20',
                'serie': 'GF99999',
                'estado': 'OPERATIVO'
            }
        )
        
        # Esto debe fallar porque ya hay un activo activo
        historial_invalido = HistorialBienAfecto(
            bien_afecto=bien_afecto,
            activo=activo4,
            usuario_alta=usuario
        )
        historial_invalido.save()
        
        print("✗ ERROR: La validación no funcionó")
    except Exception as e:
        print(f"✓ Validación funcionó correctamente")
        print(f"  - Error esperado: {str(e)}")
    
    print("\n" + "=" * 80)
    print("PRUEBAS COMPLETADAS")
    print("=" * 80)
    print(f"\n✓ Bien Afecto: {bien_afecto.codigo_interno}")
    print(f"✓ Activo actual: {bien_afecto.activo_actual.nombre if bien_afecto.activo_actual else 'Sin asignar'}")
    print(f"✓ Total de activos en historial: {bien_afecto.historial.count()}")
    print(f"✓ Total de reemplazos: {bien_afecto.historial.count() - 1}")
    
    print("\n📊 Ahora puedes ver el Bien Afecto en el admin de Django:")
    print(f"   http://localhost:8000/admin/activos/bienafecto/{bien_afecto.id}/change/")
    print("\n")

if __name__ == '__main__':
    test_bien_afecto()
