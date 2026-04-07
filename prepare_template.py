import zipfile
import re

src = 'd:/Apps/energia/energy/tiempo_acordado.docx'
dst = 'd:/Apps/energia/energy/tiempo_acordado_template.docx'

with zipfile.ZipFile(src, 'r') as z_in:
    with zipfile.ZipFile(dst, 'w') as z_out:
        for item in z_in.infolist():
            content = z_in.read(item.filename)
            if item.filename == 'word/document.xml':
                text = content.decode('utf-8')
                
                # Jinja variables replace
                text = text.replace('[FOLIO]', '{{ FOLIO }}')
                text = text.replace('[ENLACE_MAO]', '{{ ENLACE_MAO }}')
                text = text.replace('[FECHA_SOLICITUD]', '{{ FECHA_SOLICITUD }}')
                text = text.replace('[INSTITUCION]', '{{ INSTITUCION }}')
                text = text.replace('[FECHA_SOLUCION]', '{{ FECHA_SOLUCION }}')
                text = text.replace('[MOTIVO]', '{{ MOTIVO }}')
                text = text.replace('[SOLUCION_PROVISIONAL]', '{{ SOLUCION_PROVISIONAL }}')
                text = text.replace('[OBSERVACIONES]', '{{ OBSERVACIONES }}')
                
                # Image injections:
                # Add {{ GANTT }} exactly after CRONOGRAMA DE TIEMPO
                text = text.replace('CRONOGRAMA DE TIEMPO', 'CRONOGRAMA DE TIEMPO</w:t></w:r><w:r><w:br/><w:t>{{ GANTT }}')
                
                # The document has ___________________________________________
                # We want to replace the first line with {{ FIRMA_RESPONSABLE }} y luego la raya.
                # However, python strings replacement from right to left is safer for multiple instances.
                parts = text.split('___________________________________________')
                if len(parts) >= 3:
                    # parts[0] is everything before first ______
                    # parts[1] is between first and second ______
                    # parts[2] is after second ______
                    
                    # Insert FIRMA_RESPONSABLE before the first line
                    new_text = parts[0] + '{{ FIRMA_RESPONSABLE }}</w:t></w:r><w:r><w:br/><w:t>___________________________________________' + parts[1] + '{{ FIRMA_ENLACE }}</w:t></w:r><w:r><w:br/><w:t>___________________________________________' + parts[2]
                    for i in range(3, len(parts)):
                         new_text += '___________________________________________' + parts[i]
                    text = new_text
                    
                content = text.encode('utf-8')
            z_out.writestr(item, content)

print("Template preparation completed.")
