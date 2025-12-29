"""
Vistas para el Sistema de Firmas Electrónicas
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.core.files.base import ContentFile
from django.utils import timezone
import base64
import json
from io import BytesIO
from PIL import Image

from .models_firmas import (
    PerfilFirma, DocumentoFirmado, FirmaRequerida, 
    Firma, AuditoriaFirmas
)
from .models import Documento, Revision


def obtener_ip(request):
    """Obtiene la IP real del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def perfil_firma(request):
    """
    Vista para gestionar el perfil de firma del usuario
    Permite crear/actualizar firma manuscrita o subir PNG
    """
    perfil, created = PerfilFirma.objects.get_or_create(usuario=request.user)
    
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'guardar_manuscrita':
            # Firma manuscrita desde canvas (base64)
            firma_data = request.POST.get('firma_data')
            
            if firma_data:
                # Decodificar base64
                format, imgstr = firma_data.split(';base64,')
                ext = format.split('/')[-1]
                
                # Convertir a imagen
                img_data = base64.b64decode(imgstr)
                img = Image.open(BytesIO(img_data))
                
                # Convertir a PNG con fondo transparente
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Guardar
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                
                filename = f"firma_{request.user.username}.png"
                perfil.firma_imagen.save(filename, ContentFile(buffer.read()), save=False)
                
                # Actualizar metadatos
                perfil.cargo = request.POST.get('cargo', perfil.cargo)
                perfil.departamento = request.POST.get('departamento', perfil.departamento)
                perfil.save()
                
                # Auditoría
                AuditoriaFirmas.objects.create(
                    usuario=request.user,
                    accion='CREAR_PERFIL' if created else 'ACTUALIZAR_PERFIL',
                    ip=obtener_ip(request),
                    detalles={'tipo': 'manuscrita'}
                )
                
                messages.success(request, 'Firma manuscrita guardada exitosamente')
                return JsonResponse({'success': True})
        
        elif accion == 'subir_imagen':
            # Firma subida como PNG
            firma_archivo = request.FILES.get('firma_imagen')
            
            if firma_archivo:
                # Validar que sea PNG/JPG
                if not firma_archivo.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    return JsonResponse({
                        'success': False, 
                        'error': 'Solo se permiten archivos PNG o JPG'
                    })
                
                # Procesar imagen para asegurar calidad
                img = Image.open(firma_archivo)
                
                # Convertir a RGBA si no lo es
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Redimensionar si es muy grande (max 800px de ancho)
                max_width = 800
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_size = (max_width, int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Guardar
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                
                perfil.firma_imagen.save(
                    f"firma_{request.user.username}.png",
                    ContentFile(buffer.read()),
                    save=False
                )
                
                perfil.cargo = request.POST.get('cargo', perfil.cargo)
                perfil.departamento = request.POST.get('departamento', perfil.departamento)
                perfil.save()
                
                # Auditoría
                AuditoriaFirmas.objects.create(
                    usuario=request.user,
                    accion='CREAR_PERFIL' if created else 'ACTUALIZAR_PERFIL',
                    ip=obtener_ip(request),
                    detalles={'tipo': 'imagen_subida'}
                )
                
                messages.success(request, 'Firma cargada exitosamente')
                return redirect('firmas:perfil_firma')
    
    context = {
        'perfil': perfil,
    }
    return render(request, 'documentos/firmas/perfil_firma.html', context)


@login_required
def lista_documentos_por_firmar(request):
    """
    Lista de documentos pendientes de firma para el usuario actual
    """
    # Documentos que requieren la firma del usuario
    firmas_requeridas = FirmaRequerida.objects.filter(
        firmante=request.user
    ).select_related(
        'documento_firmado__documento',
        'documento_firmado__revision'
    ).exclude(
        firma_aplicada__firmado=True
    )
    
    context = {
        'firmas_pendientes': firmas_requeridas,
    }
    return render(request, 'documentos/firmas/lista_por_firmar.html', context)


@login_required
def visor_documento_firmar(request, documento_firmado_id):
    """
    Visor de documento con interfaz para estampar firma
    """
    doc_firmado = get_object_or_404(DocumentoFirmado, pk=documento_firmado_id)
    
    # Verificar que el usuario tiene una firma requerida para este documento
    firma_requerida = FirmaRequerida.objects.filter(
        documento_firmado=doc_firmado,
        firmante=request.user
    ).first()
    
    if not firma_requerida:
        messages.error(request, 'No tienes autorización para firmar este documento')
        return redirect('firmas:lista_por_firmar')
    
    # Verificar si ya firmó
    if hasattr(firma_requerida, 'firma_aplicada') and firma_requerida.firma_aplicada:
        messages.info(request, 'Ya has firmado este documento')
        return redirect('firmas:lista_por_firmar')
    
    # Obtener perfil de firma del usuario
    perfil_firma = PerfilFirma.objects.filter(usuario=request.user).first()
    
    if not perfil_firma or not perfil_firma.firma_imagen:
        messages.warning(
            request, 
            'Debes configurar tu firma primero antes de firmar documentos'
        )
        return redirect('firmas:perfil_firma')
    
    # Obtener todas las firmas ya aplicadas al documento
    firmas_existentes = doc_firmado.firmas.filter(firmado=True)
    
    context = {
        'documento_firmado': doc_firmado,
        'firma_requerida': firma_requerida,
        'perfil_firma': perfil_firma,
        'firmas_existentes': firmas_existentes,
    }
    return render(request, 'documentos/firmas/visor_firmar.html', context)


@login_required
@require_POST
def aplicar_firma(request, documento_firmado_id):
    """
    Aplica la firma electrónica al documento
    """
    doc_firmado = get_object_or_404(DocumentoFirmado, pk=documento_firmado_id)
    
    # Verificar autorización
    firma_requerida = FirmaRequerida.objects.filter(
        documento_firmado=doc_firmado,
        firmante=request.user
    ).first()
    
    if not firma_requerida:
        return JsonResponse({
            'success': False,
            'error': 'No autorizado para firmar este documento'
        })
    
    # Verificar si ya firmó
    if hasattr(firma_requerida, 'firma_aplicada'):
        return JsonResponse({
            'success': False,
            'error': 'Ya has firmado este documento'
        })
    
    try:
        # Obtener datos de la firma
        data = json.loads(request.body)
        posicion_x = float(data.get('posicion_x', firma_requerida.posicion_x))
        posicion_y = float(data.get('posicion_y', firma_requerida.posicion_y))
        pagina = int(data.get('pagina', firma_requerida.pagina))
        comentarios = data.get('comentarios', '')
        
        # Obtener perfil de firma
        perfil_firma = get_object_or_404(PerfilFirma, usuario=request.user)
        
        if not perfil_firma.firma_imagen:
            return JsonResponse({
                'success': False,
                'error': 'No tienes una firma configurada'
            })
        
        with transaction.atomic():
            # Crear registro de firma
            firma = Firma.objects.create(
                documento_firmado=doc_firmado,
                firma_requerida=firma_requerida,
                firmante=request.user,
                imagen_firma=perfil_firma.firma_imagen,
                posicion_x=posicion_x,
                posicion_y=posicion_y,
                pagina=pagina,
                ancho=firma_requerida.ancho,
                alto=firma_requerida.alto,
                ip_firmante=obtener_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                comentarios=comentarios,
                firmado=True,
            )
            
            # Auditoría
            AuditoriaFirmas.objects.create(
                usuario=request.user,
                accion='FIRMAR',
                documento_firmado=doc_firmado,
                firma=firma,
                ip=obtener_ip(request),
                detalles={
                    'posicion': {'x': posicion_x, 'y': posicion_y, 'pagina': pagina},
                    'comentarios': comentarios
                }
            )
            
            # Generar certificado
            certificado = firma.generar_certificado_autenticidad()
        
        return JsonResponse({
            'success': True,
            'message': 'Documento firmado exitosamente',
            'token_verificacion': str(firma.token_verificacion),
            'certificado': certificado
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def rechazar_firma(request, documento_firmado_id):
    """
    Rechaza la firma de un documento
    """
    doc_firmado = get_object_or_404(DocumentoFirmado, pk=documento_firmado_id)
    
    # Verificar autorización
    firma_requerida = FirmaRequerida.objects.filter(
        documento_firmado=doc_firmado,
        firmante=request.user
    ).first()
    
    if not firma_requerida:
        return JsonResponse({
            'success': False,
            'error': 'No autorizado'
        })
    
    try:
        data = json.loads(request.body)
        motivo = data.get('motivo', '')
        
        with transaction.atomic():
            # Crear firma de rechazo
            firma = Firma.objects.create(
                documento_firmado=doc_firmado,
                firma_requerida=firma_requerida,
                firmante=request.user,
                posicion_x=0,
                posicion_y=0,
                pagina=1,
                ip_firmante=obtener_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                firmado=False,
                rechazado=True,
                motivo_rechazo=motivo
            )
            
            # Auditoría
            AuditoriaFirmas.objects.create(
                usuario=request.user,
                accion='RECHAZAR',
                documento_firmado=doc_firmado,
                firma=firma,
                ip=obtener_ip(request),
                detalles={'motivo': motivo}
            )
        
        return JsonResponse({
            'success': True,
            'message': 'Firma rechazada'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def verificar_firma(request, token):
    """
    Verifica la autenticidad de una firma mediante su token
    """
    try:
        firma = get_object_or_404(Firma, token_verificacion=token)
        
        # Verificar integridad del documento
        integridad_valida = firma.documento_firmado.verificar_integridad()
        
        # Auditoría
        AuditoriaFirmas.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            accion='VERIFICAR',
            documento_firmado=firma.documento_firmado,
            firma=firma,
            ip=obtener_ip(request),
            detalles={'integridad_valida': integridad_valida}
        )
        
        context = {
            'firma': firma,
            'integridad_valida': integridad_valida,
            'certificado': firma.generar_certificado_autenticidad(),
        }
        return render(request, 'documentos/firmas/verificar_firma.html', context)
    
    except Firma.DoesNotExist:
        messages.error(request, 'Firma no encontrada o token inválido')
        return render(request, 'documentos/firmas/verificar_firma.html', {
            'firma': None,
            'integridad_valida': False
        })


@login_required
def solicitar_firmas(request, documento_id):
    """
    Interfaz para configurar firmantes y sus posiciones en un documento
    """
    documento = get_object_or_404(Documento, pk=documento_id)
    
    # Obtener o crear DocumentoFirmado
    # Buscar si ya existe un DocumentoFirmado para esta revisión
    doc_firmado = DocumentoFirmado.objects.filter(
        documento=documento,
        revision=documento.ultima_revision
    ).first()
    
    created = False
    if not doc_firmado:
        doc_firmado = DocumentoFirmado.objects.create(
            documento=documento,
            revision=documento.ultima_revision
        )
        created = True
    
    if request.method == 'POST':
        # Procesar solicitud de firmas
        firmantes_data = json.loads(request.POST.get('firmantes'))
        
        with transaction.atomic():
            # Limpiar firmas requeridas anteriores si es nuevo
            if created:
                doc_firmado.firmas_requeridas.all().delete()
            
            # Crear firmas requeridas
            for idx, firmante_info in enumerate(firmantes_data, 1):
                FirmaRequerida.objects.create(
                    documento_firmado=doc_firmado,
                    firmante_id=firmante_info['usuario_id'],
                    orden=idx,
                    rol=firmante_info.get('rol', ''),
                    posicion_x=firmante_info.get('x', 10),
                    posicion_y=firmante_info.get('y', 10),
                    pagina=firmante_info.get('pagina', 1),
                    ancho=firmante_info.get('ancho', 15),
                    alto=firmante_info.get('alto', 8),
                    obligatoria=firmante_info.get('obligatoria', True)
                )
            
            # Auditoría
            AuditoriaFirmas.objects.create(
                usuario=request.user,
                accion='SOLICITAR_FIRMA',
                documento_firmado=doc_firmado,
                ip=obtener_ip(request),
                detalles={'num_firmantes': len(firmantes_data)}
            )
            
            messages.success(request, 'Solicitud de firmas creada exitosamente')
            return redirect('firmas:lista_documentos_firmados')
    
    # Obtener usuarios disponibles para firmar
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
    
    context = {
        'documento': documento,
        'doc_firmado': doc_firmado,
        'usuarios': usuarios,
        'firmas_requeridas': doc_firmado.firmas_requeridas.all()
    }
    return render(request, 'documentos/firmas/solicitar_firmas.html', context)


@login_required
def lista_documentos_firmados(request):
    """
    Lista todos los documentos firmados (o en proceso de firma)
    """
    documentos = DocumentoFirmado.objects.select_related(
        'documento',
        'revision'
    ).prefetch_related(
        'firmas_requeridas',
        'firmas'
    ).order_by('-creado_en')
    
    context = {
        'documentos': documentos,
    }
    return render(request, 'documentos/firmas/lista_documentos_firmados.html', context)


@login_required
def generar_pdf_firmado(request, documento_firmado_id):
    """
    Genera el PDF con las firmas estampadas visualmente
    """
    doc_firmado = get_object_or_404(DocumentoFirmado, pk=documento_firmado_id)
    
    try:
        from .utils_pdf import generar_pdf_firmado as gen_pdf
        
        exito = gen_pdf(doc_firmado)
        
        if exito:
            messages.success(request, 'PDF firmado generado exitosamente')
            
            # Auditoría
            AuditoriaFirmas.objects.create(
                usuario=request.user,
                accion='GENERAR_PDF',
                documento_firmado=doc_firmado,
                ip=obtener_ip(request),
                detalles={'exito': True}
            )
        else:
            messages.error(request, 'Error al generar el PDF firmado')
    
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('firmas:lista_documentos_firmados')


@login_required
def descargar_pdf_firmado(request, documento_firmado_id):
    """
    Descarga el PDF con firmas estampadas
    """
    doc_firmado = get_object_or_404(DocumentoFirmado, pk=documento_firmado_id)
    
    # Si no existe el PDF firmado, generarlo primero
    if not doc_firmado.pdf_firmado:
        from .utils_pdf import generar_pdf_firmado as gen_pdf
        gen_pdf(doc_firmado)
        doc_firmado.refresh_from_db()
    
    if doc_firmado.pdf_firmado:
        response = FileResponse(
            doc_firmado.pdf_firmado.open('rb'),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{doc_firmado.documento.codigo}_firmado.pdf"'
        
        # Auditoría
        AuditoriaFirmas.objects.create(
            usuario=request.user,
            accion='GENERAR_PDF',
            documento_firmado=doc_firmado,
            ip=obtener_ip(request),
            detalles={'accion': 'descarga'}
        )
        
        return response
    else:
        messages.error(request, 'No se pudo generar el PDF firmado')
        return redirect('firmas:lista_documentos_firmados')


@login_required
def ver_pdf_firmado(request, documento_firmado_id):
    """
    Visualiza el PDF con firmas en el navegador
    """
    doc_firmado = get_object_or_404(DocumentoFirmado, pk=documento_firmado_id)
    
    # Si no existe el PDF firmado, generarlo primero
    if not doc_firmado.pdf_firmado:
        from .utils_pdf import generar_pdf_firmado as gen_pdf
        gen_pdf(doc_firmado)
        doc_firmado.refresh_from_db()
    
    if doc_firmado.pdf_firmado:
        response = FileResponse(
            doc_firmado.pdf_firmado.open('rb'),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'inline; filename="{doc_firmado.documento.codigo}_firmado.pdf"'
        return response
    else:
        messages.error(request, 'No se pudo generar el PDF firmado')
        return redirect('firmas:lista_documentos_firmados')


@login_required
def descargar_certificado_firma(request, firma_id):
    """
    Descarga el certificado de autenticidad de una firma en PDF
    """
    firma = get_object_or_404(Firma, pk=firma_id)
    
    try:
        from .utils_pdf import generar_certificado_pdf
        
        pdf_buffer = generar_certificado_pdf(firma)
        
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="certificado_{firma.token_verificacion}.pdf"'
        
        # Auditoría
        AuditoriaFirmas.objects.create(
            usuario=request.user,
            accion='VERIFICAR',
            documento_firmado=firma.documento_firmado,
            firma=firma,
            ip=obtener_ip(request),
            detalles={'accion': 'descarga_certificado'}
        )
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al generar certificado: {str(e)}')
        return redirect('firmas:lista_documentos_firmados')

