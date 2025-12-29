"""
Ejemplos de Uso del Sistema de Firmas Electrónicas
==================================================

Este archivo contiene ejemplos prácticos de cómo usar el sistema de firmas
programáticamente desde Python/Django.
"""

from django.contrib.auth.models import User
from documentos.models import Documento
from documentos.models_firmas import (
    PerfilFirma, DocumentoFirmado, FirmaRequerida, Firma
)
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO


# ============================================================================
# EJEMPLO 1: Crear un perfil de firma para un usuario
# ============================================================================

def crear_perfil_firma_ejemplo():
    """
    Crea un perfil de firma para un usuario
    """
    usuario = User.objects.get(username='juan.perez')
    
    # Crear perfil
    perfil = PerfilFirma.objects.create(
        usuario=usuario,
        cargo='Ingeniero Senior',
        departamento='Ingeniería de Proyectos',
        activa=True
    )
    
    # Aquí normalmente se cargaría una imagen de firma
    # Por ahora solo creamos el perfil sin imagen
    
    print(f"✅ Perfil creado para {usuario.get_full_name()}")
    return perfil


# ============================================================================
# EJEMPLO 2: Solicitar firmas para un documento
# ============================================================================

def solicitar_firmas_ejemplo():
    """
    Crea una solicitud de firmas para un documento con múltiples firmantes
    """
    # Obtener el documento
    documento = Documento.objects.get(codigo='ENG-PLN-001')
    
    # Crear DocumentoFirmado
    doc_firmado = DocumentoFirmado.objects.create(
        documento=documento,
        revision=documento.ultima_revision,
        estado='PENDIENTE'
    )
    
    print(f"📄 Documento preparado: {documento.codigo}")
    
    # Definir firmantes con sus roles
    firmantes = [
        {
            'usuario': User.objects.get(username='ingeniero1'),
            'rol': 'Elaboró',
            'orden': 1,
            'x': 10,
            'y': 85,
            'pagina': 1
        },
        {
            'usuario': User.objects.get(username='supervisor'),
            'rol': 'Revisó',
            'orden': 2,
            'x': 40,
            'y': 85,
            'pagina': 1
        },
        {
            'usuario': User.objects.get(username='gerente'),
            'rol': 'Aprobó',
            'orden': 3,
            'x': 70,
            'y': 85,
            'pagina': 1
        }
    ]
    
    # Crear FirmaRequerida para cada firmante
    for f in firmantes:
        firma_req = FirmaRequerida.objects.create(
            documento_firmado=doc_firmado,
            firmante=f['usuario'],
            rol=f['rol'],
            orden=f['orden'],
            posicion_x=f['x'],
            posicion_y=f['y'],
            pagina=f['pagina'],
            ancho=15,
            alto=8,
            obligatoria=True
        )
        print(f"  👤 {f['usuario'].get_full_name()} - {f['rol']}")
    
    print(f"\n✅ {len(firmantes)} firmas solicitadas")
    return doc_firmado


# ============================================================================
# EJEMPLO 3: Aplicar firma programáticamente
# ============================================================================

def aplicar_firma_ejemplo():
    """
    Aplica una firma a un documento de forma programática
    """
    # Obtener documento firmado y firma requerida
    doc_firmado = DocumentoFirmado.objects.get(documento__codigo='ENG-PLN-001')
    usuario = User.objects.get(username='ingeniero1')
    
    firma_requerida = FirmaRequerida.objects.get(
        documento_firmado=doc_firmado,
        firmante=usuario
    )
    
    # Obtener perfil de firma del usuario
    perfil = PerfilFirma.objects.get(usuario=usuario)
    
    # Crear la firma
    firma = Firma.objects.create(
        documento_firmado=doc_firmado,
        firma_requerida=firma_requerida,
        firmante=usuario,
        imagen_firma=perfil.firma_imagen,
        posicion_x=firma_requerida.posicion_x,
        posicion_y=firma_requerida.posicion_y,
        pagina=firma_requerida.pagina,
        ancho=firma_requerida.ancho,
        alto=firma_requerida.alto,
        ip_firmante='192.168.1.100',
        user_agent='Python Script',
        firmado=True,
        comentarios='Firmado programáticamente'
    )
    
    print(f"✅ Firma aplicada por {usuario.get_full_name()}")
    print(f"   Token: {firma.token_verificacion}")
    print(f"   Hash: {firma.hash_firma}")
    
    return firma


# ============================================================================
# EJEMPLO 4: Verificar integridad de un documento
# ============================================================================

def verificar_integridad_ejemplo():
    """
    Verifica que un documento no ha sido modificado después de firmado
    """
    doc_firmado = DocumentoFirmado.objects.get(documento__codigo='ENG-PLN-001')
    
    es_integro = doc_firmado.verificar_integridad()
    
    if es_integro:
        print("✅ Documento íntegro - No ha sido modificado")
    else:
        print("⚠️ ADVERTENCIA: Documento modificado después de firmar")
    
    print(f"   Hash almacenado: {doc_firmado.hash_documento_original}")
    print(f"   Hash actual: {doc_firmado.calcular_hash_documento()}")
    
    return es_integro


# ============================================================================
# EJEMPLO 5: Obtener certificado de autenticidad
# ============================================================================

def obtener_certificado_ejemplo():
    """
    Obtiene el certificado de autenticidad de una firma
    """
    # Buscar firma por token
    token = 'abc123...'  # Token UUID de ejemplo
    
    try:
        firma = Firma.objects.get(token_verificacion=token)
        certificado = firma.generar_certificado_autenticidad()
        
        import json
        print("📜 Certificado de Autenticidad:")
        print(json.dumps(certificado, indent=2, ensure_ascii=False))
        
        return certificado
        
    except Firma.DoesNotExist:
        print("❌ Firma no encontrada con ese token")
        return None


# ============================================================================
# EJEMPLO 6: Rechazar un documento
# ============================================================================

def rechazar_documento_ejemplo():
    """
    Rechaza un documento con motivo
    """
    doc_firmado = DocumentoFirmado.objects.get(documento__codigo='ENG-PLN-001')
    usuario = User.objects.get(username='supervisor')
    
    firma_requerida = FirmaRequerida.objects.get(
        documento_firmado=doc_firmado,
        firmante=usuario
    )
    
    # Crear firma de rechazo
    firma_rechazo = Firma.objects.create(
        documento_firmado=doc_firmado,
        firma_requerida=firma_requerida,
        firmante=usuario,
        posicion_x=0,
        posicion_y=0,
        pagina=1,
        ip_firmante='192.168.1.100',
        user_agent='Python Script',
        firmado=False,
        rechazado=True,
        motivo_rechazo='El documento contiene errores en la sección 3.2'
    )
    
    print(f"❌ Documento rechazado por {usuario.get_full_name()}")
    print(f"   Motivo: {firma_rechazo.motivo_rechazo}")
    
    return firma_rechazo


# ============================================================================
# EJEMPLO 7: Consultar estado de un documento
# ============================================================================

def consultar_estado_ejemplo():
    """
    Consulta el estado de firmas de un documento
    """
    doc_firmado = DocumentoFirmado.objects.get(documento__codigo='ENG-PLN-001')
    
    total_firmas = doc_firmado.firmas_requeridas.count()
    firmas_aplicadas = doc_firmado.firmas.filter(firmado=True).count()
    firmas_rechazadas = doc_firmado.firmas.filter(rechazado=True).count()
    
    print(f"📊 Estado del Documento: {doc_firmado.documento.codigo}")
    print(f"   Estado: {doc_firmado.get_estado_display()}")
    print(f"   Progreso: {firmas_aplicadas}/{total_firmas} firmas")
    
    if firmas_rechazadas > 0:
        print(f"   ⚠️ Rechazos: {firmas_rechazadas}")
    
    # Listar firmantes pendientes
    print("\n   Firmantes:")
    for firma_req in doc_firmado.firmas_requeridas.all():
        if hasattr(firma_req, 'firma_aplicada'):
            if firma_req.firma_aplicada.firmado:
                estado = f"✅ Firmado ({firma_req.firma_aplicada.fecha_firma})"
            elif firma_req.firma_aplicada.rechazado:
                estado = f"❌ Rechazado"
        else:
            estado = "⏳ Pendiente"
        
        print(f"   - {firma_req.firmante.get_full_name()} ({firma_req.rol}): {estado}")


# ============================================================================
# EJEMPLO 8: Buscar documentos pendientes de firma de un usuario
# ============================================================================

def documentos_pendientes_usuario(username):
    """
    Obtiene todos los documentos pendientes de firma de un usuario
    """
    usuario = User.objects.get(username=username)
    
    firmas_pendientes = FirmaRequerida.objects.filter(
        firmante=usuario
    ).exclude(
        firma_aplicada__firmado=True
    ).select_related('documento_firmado__documento')
    
    print(f"📋 Documentos pendientes para {usuario.get_full_name()}:")
    print(f"   Total: {firmas_pendientes.count()}")
    print()
    
    for firma_req in firmas_pendientes:
        doc = firma_req.documento_firmado.documento
        print(f"   📄 {doc.codigo}")
        print(f"      {doc.titulo}")
        print(f"      Rol: {firma_req.rol}")
        if firma_req.obligatoria:
            print(f"      ⚠️ OBLIGATORIA")
        print()
    
    return firmas_pendientes


# ============================================================================
# EJEMPLO 9: Workflow completo de firma
# ============================================================================

def workflow_completo_ejemplo():
    """
    Ejemplo de workflow completo de principio a fin
    """
    print("=" * 60)
    print("WORKFLOW COMPLETO DE FIRMA ELECTRÓNICA")
    print("=" * 60)
    
    # 1. Crear documento (asumimos que ya existe)
    documento = Documento.objects.first()
    print(f"\n1️⃣ Documento: {documento.codigo}")
    
    # 2. Solicitar firmas
    print(f"\n2️⃣ Solicitando firmas...")
    doc_firmado = DocumentoFirmado.objects.create(
        documento=documento,
        revision=documento.ultima_revision
    )
    
    # Agregar firmantes
    usuario1 = User.objects.first()
    usuario2 = User.objects.all()[1] if User.objects.count() > 1 else usuario1
    
    FirmaRequerida.objects.create(
        documento_firmado=doc_firmado,
        firmante=usuario1,
        rol='Elaboró',
        orden=1,
        posicion_x=10,
        posicion_y=85,
        pagina=1
    )
    
    FirmaRequerida.objects.create(
        documento_firmado=doc_firmado,
        firmante=usuario2,
        rol='Aprobó',
        orden=2,
        posicion_x=60,
        posicion_y=85,
        pagina=1
    )
    
    print(f"   ✅ {doc_firmado.firmas_requeridas.count()} firmantes agregados")
    
    # 3. Estado inicial
    print(f"\n3️⃣ Estado inicial:")
    print(f"   {doc_firmado.get_estado_display()}")
    
    # 4. Primera firma
    print(f"\n4️⃣ Aplicando primera firma...")
    # (Aquí normalmente se llamaría a la vista de firma)
    print(f"   ✅ Usuario 1 firma como 'Elaboró'")
    
    # 5. Estado parcial
    print(f"\n5️⃣ Estado actual:")
    print(f"   PARCIAL (1/2 firmas)")
    
    # 6. Segunda firma
    print(f"\n6️⃣ Aplicando segunda firma...")
    print(f"   ✅ Usuario 2 firma como 'Aprobó'")
    
    # 7. Estado final
    print(f"\n7️⃣ Estado final:")
    print(f"   COMPLETO (2/2 firmas) ✅")
    
    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETADO EXITOSAMENTE")
    print("=" * 60)


# ============================================================================
# EJEMPLO 10: Generar reporte de auditoría
# ============================================================================

def reporte_auditoria_ejemplo():
    """
    Genera un reporte de auditoría de firmas
    """
    from documentos.models_firmas import AuditoriaFirmas
    from django.utils import timezone
    from datetime import timedelta
    
    # Últimas 24 horas
    hace_24h = timezone.now() - timedelta(hours=24)
    auditorias = AuditoriaFirmas.objects.filter(
        fecha__gte=hace_24h
    ).order_by('-fecha')
    
    print("📊 REPORTE DE AUDITORÍA (Últimas 24h)")
    print("=" * 60)
    print(f"Total de eventos: {auditorias.count()}\n")
    
    # Agrupar por acción
    acciones = {}
    for audit in auditorias:
        accion = audit.get_accion_display()
        if accion not in acciones:
            acciones[accion] = 0
        acciones[accion] += 1
    
    print("Por tipo de acción:")
    for accion, count in acciones.items():
        print(f"  {accion}: {count}")
    
    print("\nÚltimos 10 eventos:")
    for audit in auditorias[:10]:
        print(f"  [{audit.fecha.strftime('%H:%M:%S')}] {audit.usuario.username if audit.usuario else 'Sistema'}")
        print(f"  {audit.get_accion_display()}")
        print(f"  IP: {audit.ip or 'N/A'}")
        print()


# ============================================================================
# Para ejecutar estos ejemplos:
# ============================================================================
"""
# En Django shell:
python manage.py shell

# Luego importar y ejecutar:
from documentos.ejemplos_firmas import *

# Ejemplos:
crear_perfil_firma_ejemplo()
solicitar_firmas_ejemplo()
aplicar_firma_ejemplo()
verificar_integridad_ejemplo()
obtener_certificado_ejemplo()
rechazar_documento_ejemplo()
consultar_estado_ejemplo()
documentos_pendientes_usuario('juan.perez')
workflow_completo_ejemplo()
reporte_auditoria_ejemplo()
"""
