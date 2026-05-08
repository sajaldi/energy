# Configuración de Sincronización con Dynamics 365 / Dataverse

SYNC_CONFIG = {
    # Inventarios - Materiales
    'inventarios.Material': {
        'entity': 'cr8ca_materiales',
        'fields': ['nombre', 'sku', 'descripcion', 'precio_estimado', 'stock_minimo'],
        'mapping': {
            'nombre': 'cr8ca_nombre',
            'sku': 'cr8ca_sku',
            'descripcion': 'cr8ca_descripcion',
            'precio_estimado': 'cr8ca_precio',
        }
    },
    
    # Mantenimiento - Órdenes de Trabajo
    'mantenimiento.OrdenTrabajo': {
        'entity': 'cr8ca_ordenestrabajo',
        'fields': ['id', 'descripcion', 'fecha_programada', 'estado'],
        'mapping': {
            'id': 'cr8ca_foliodjango',
            'descripcion': 'cr8ca_descripcion',
            'fecha_programada': 'cr8ca_fechaprogramada',
            'estado': 'cr8ca_estado'
        }
    },
    
    # Presupuestos - Requisiciones (Sincronización de salida como backup)
    'presupuestos.Requisicion': {
        'entity': 'cr8ca_requisiciones_backup',
        'fields': ['cr8ca_requisicion', 'cr8ca_asunto', 'cr8ca_motivo', 'estado_requisicion'],
        'mapping': {
            'cr8ca_requisicion': 'cr8ca_nombre',
            'estado_requisicion': 'cr8ca_estado'
        }
    }
}
