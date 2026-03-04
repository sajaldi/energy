import sys, re

with open('d:/Apps/energia/energy/mantenimiento/admin.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Imports
text = text.replace('Procedimiento, PasoProcedimiento,', 'PasoRutina,')
text = text.replace('Procedimiento, PasoProcedimiento', 'PasoRutina')

# 2. RutinaInline
text = text.replace("'tiempo_estimado', 'cantidad_tecnicos', 'procedimiento_estandar'", "'tiempo_estimado', 'cantidad_tecnicos'")
text = text.replace("'frecuencia', 'procedimiento_estandar'", "'frecuencia'")

# 3. ProcedimientoResource and PasoProcedimientoResource
text = re.sub(r'# --- RESOURCES PARA PROCEDIMIENTOS ---\nclass ProcedimientoResource.*?# --- RESOURCE PERSONALIZADO PARA TÉCNICOS ---', '# --- RESOURCE PERSONALIZADO PARA TÉCNICOS ---', text, flags=re.DOTALL)

# 4. RutinaResource
text = re.sub(r'    procedimiento_estandar = fields\.Field\(\n        column_name=\'procedimiento_estandar\',\n        attribute=\'procedimiento_estandar\',\n        widget=ForeignKeyWidget\(Procedimiento, field=\'nombre\'\)\n    \)\n\n', '', text)
text = text.replace("'frecuencia_nombre', 'procedimiento_estandar', 'descripcion'", "'frecuencia_nombre', 'descripcion'")
text = text.replace("'frecuencia_nombre', 'procedimiento_estandar', 'tiempo_estimado'", "'frecuencia_nombre', 'tiempo_estimado'")

# 5. PasoProcedimientoInline & ProcedimientoAdmin
# Line 1134
paso_procedimiento_inline = '''class PasoProcedimientoInline(admin.TabularInline):
    model = PasoProcedimiento
    extra = 1
    fields = ('orden', 'descripcion', 'tipo_respuesta', 'unidad_medida', 'valor_objetivo', 'rango_min', 'rango_max', 'punto_medicion_exacto', 'punto_medicion_codigo')'''

paso_rutina_inline = '''class PasoRutinaInline(admin.TabularInline):
    model = PasoRutina
    extra = 1
    fields = ('orden', 'descripcion', 'tipo_respuesta', 'unidad_medida', 'valor_objetivo', 'rango_min', 'rango_max', 'punto_medicion_exacto', 'punto_medicion_codigo')'''

text = text.replace(paso_procedimiento_inline, paso_rutina_inline)

# Remove ProcedimientoAdmin entirely
text = re.sub(r'@admin\.register\(Procedimiento\)\nclass ProcedimientoAdmin\(ImportExportModelAdmin\):.*?class OrdenTrabajoInline', 'class OrdenTrabajoInline', text, flags=re.DOTALL)

# 6. RutinaAdmin
text = text.replace("'codigo_rutina', 'nombre', 'procedimiento_estandar__nombre', 'herramientas'", "'codigo_rutina', 'nombre', 'herramientas'")
text = text.replace("'tipo', 'frecuencia', 'procedimiento_estandar', 'puesto_trabajo'", "'tipo', 'frecuencia', 'puesto_trabajo'")
text = text.replace("'fields': ('procedimiento_estandar', 'herramientas')", "'fields': ('herramientas',)")
text = text.replace("inlines = [ProgramacionInline] # Agregado historial de programaciones", "inlines = [PasoRutinaInline, ProgramacionInline] # Agregado historial de programaciones")

# 7. ValorPasoOrden
text = text.replace('ValorPasoOrdenInline(admin.TabularInline):\n    model = ValorPasoOrden\n    extra = 0\n    raw_id_fields = (\'paso\', \'capturado_por\')', 'ValorPasoOrdenInline(admin.TabularInline):\n    model = ValorPasoOrden\n    extra = 0\n    raw_id_fields = (\'paso\', \'capturado_por\')') # no change needed for ValorPasoOrden admin, but good to check

with open('d:/Apps/energia/energy/mantenimiento/admin.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Refactoring admin.py complete.")
