"""
URLs para el Sistema de Firmas Electrónicas
"""

from django.urls import path
from . import views_firmas

app_name = 'firmas'

urlpatterns = [
    # Perfil de firma del usuario
    path('perfil/', views_firmas.perfil_firma, name='perfil_firma'),
    
    # Lista de documentos por firmar
    path('por-firmar/', views_firmas.lista_documentos_por_firmar, name='lista_por_firmar'),
    
    # Visor para firmar un documento
    path('firmar/<int:documento_firmado_id>/', views_firmas.visor_documento_firmar, name='visor_firmar'),
    
    # Aplicar firma (AJAX)
    path('aplicar/<int:documento_firmado_id>/', views_firmas.aplicar_firma, name='aplicar_firma'),
    
    # Rechazar firma (AJAX)
    path('rechazar/<int:documento_firmado_id>/', views_firmas.rechazar_firma, name='rechazar_firma'),
    
    # Verificar autenticidad de firma
    path('verificar/<uuid:token>/', views_firmas.verificar_firma, name='verificar_firma'),
    
    # Solicitar firmas para un documento
    path('solicitar/<int:documento_id>/', views_firmas.solicitar_firmas, name='solicitar_firmas'),
    
    # Lista de documentos firmados
    path('documentos/', views_firmas.lista_documentos_firmados, name='lista_documentos_firmados'),
    
    # === NUEVAS URLs para PDFs ===
    # Generar PDF firmado
    path('generar-pdf/<int:documento_firmado_id>/', views_firmas.generar_pdf_firmado, name='generar_pdf_firmado'),
    
    # Descargar PDF firmado
    path('descargar-pdf/<int:documento_firmado_id>/', views_firmas.descargar_pdf_firmado, name='descargar_pdf_firmado'),
    
    # Ver PDF firmado en navegador
    path('ver-pdf/<int:documento_firmado_id>/', views_firmas.ver_pdf_firmado, name='ver_pdf_firmado'),
    
    # Descargar certificado de firma
    path('certificado/<int:firma_id>/', views_firmas.descargar_certificado_firma, name='descargar_certificado'),
]
