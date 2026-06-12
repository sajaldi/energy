import os
import io
import copy
from datetime import datetime
import docx
import lxml.etree
from django.conf import settings

namespaces = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml'
}

def set_simple_sdt(doc, tag_name, text):
    xpath_query = f'//w:sdt[w:sdtPr/w:tag[@w:val="{tag_name}"]] | //w:sdt[w:sdtPr/w:alias[@w:val="{tag_name}"]]'
    elements = lxml.etree._Element.xpath(doc._element, xpath_query, namespaces=namespaces)
    for sdt in elements:
        content = sdt.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdtContent')
        if content is not None:
            t_els = content.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            if t_els:
                t_els[0].text = str(text) if text is not None else ""
                for t in t_els[1:]:
                    t.text = ""
            
            sdtPr = sdt.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdtPr')
            if sdtPr is not None:
                plc = sdtPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}showingPlcHdr')
                if plc is not None:
                    sdtPr.remove(plc)
            
            for r in content.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
                rPr = r.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
                if rPr is not None:
                    rStyle = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rStyle')
                    if rStyle is not None:
                        rPr.remove(rStyle)

def fill_cell(item_el, tag_name, text):
    cell_sdts = lxml.etree._Element.xpath(item_el, f'.//w:sdt[w:sdtPr/w:tag[@w:val="{tag_name}"]]', namespaces=namespaces)
    for sdt in cell_sdts:
        content = sdt.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdtContent')
        if content is not None:
            t_els = content.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            if t_els:
                t_els[0].text = str(text) if text is not None else ""
                for t in t_els[1:]:
                    t.text = ""
            
            sdtPr = sdt.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdtPr')
            if sdtPr is not None:
                plc = sdtPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}showingPlcHdr')
                if plc is not None:
                    sdtPr.remove(plc)
            
            for r in content.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
                rPr = r.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
                if rPr is not None:
                    rStyle = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rStyle')
                    if rStyle is not None:
                        rPr.remove(rStyle)

def generate_requisicion_docx(requisicion):
    template_path = os.path.join(settings.BASE_DIR, 'plantilla_files', 'PlantillaRequisicion.docx')
    doc = docx.Document(template_path)
    
    solicitante = requisicion.usuario_solicitante
    perfil_sol = getattr(solicitante, 'perfil', None) if solicitante else None
    
    solicitante_nombre = ""
    if solicitante:
        solicitante_nombre = f"{solicitante.first_name} {solicitante.last_name}".strip()
        if not solicitante_nombre:
            solicitante_nombre = solicitante.username
    else:
        solicitante_nombre = "N/A"
        
    departamento = perfil_sol.departamento.nombre if (perfil_sol and perfil_sol.departamento) else "N/A"
    fecha_sol = requisicion.fecha.strftime('%d/%m/%Y %H:%M') if requisicion.fecha else ''
    asunto = requisicion.cr8ca_asunto or "N/A"
    prioridad = requisicion.get_cr8ca_prioridad_display() if hasattr(requisicion, 'get_cr8ca_prioridad_display') else "Normal"
    motivo = requisicion.cr8ca_motivo or ""
    
    aprobador_nombre = "Gerencia"
    if perfil_sol and perfil_sol.responsable:
        aprobador_nombre = perfil_sol.responsable.get_full_name() or perfil_sol.responsable.username
        
    recibe_nombre = "Control de Procura"
    
    fecha_iso = datetime.now().strftime('%Y%m%d%H%M')
    numero_tx = f"{requisicion.cr8ca_requisicion}-{fecha_iso}"
    
    set_simple_sdt(doc, 'SolicitanteNombre', solicitante_nombre)
    set_simple_sdt(doc, 'Correlativo', requisicion.cr8ca_requisicion)
    set_simple_sdt(doc, 'Departamento', departamento)
    set_simple_sdt(doc, 'Fecha', fecha_sol)
    set_simple_sdt(doc, 'Asunto', asunto)
    set_simple_sdt(doc, 'Prioridad', prioridad)
    set_simple_sdt(doc, 'motivo', motivo)
    set_simple_sdt(doc, 'Autoriza', aprobador_nombre)
    set_simple_sdt(doc, 'Recibe', recibe_nombre)
    set_simple_sdt(doc, 'NumeroTx', numero_tx)
    
    # Fill repeating items
    items_sdt_list = lxml.etree._Element.xpath(doc._element, '//w:sdt[w:sdtPr/w:tag[@w:val="items"]]', namespaces=namespaces)
    if items_sdt_list:
        items_sdt = items_sdt_list[0]
        content = items_sdt.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdtContent')
        if content is not None:
            repeating_items = lxml.etree._Element.xpath(content, 'w:sdt[w:sdtPr/w15:repeatingSectionItem]', namespaces=namespaces)
            if repeating_items:
                template_item = repeating_items[0]
                
                # Remove extra repeating items
                for item in repeating_items[1:]:
                    content.remove(item)
                
                articulos = requisicion.articulos.all()
                if articulos:
                    current_item = template_item
                    for idx, art in enumerate(articulos):
                        if idx > 0:
                            new_item = copy.deepcopy(template_item)
                            content.append(new_item)
                            current_item = new_item
                            
                        cantidad_val = f"{float(art.cr8ca_cantidad or 0):g}"
                        unidad_val = art.material.unidad_medida.abreviatura if (art.material and art.material.unidad_medida) else 'UND'
                        desc_val = art.cr8ca_articulo or ""
                        comentario_val = art.proveedor.nombre if art.proveedor else ""
                        
                        fill_cell(current_item, 'Cantidad', cantidad_val)
                        fill_cell(current_item, 'Unidades', unidad_val)
                        fill_cell(current_item, 'Producto', desc_val)
                        fill_cell(current_item, 'Comentario', comentario_val)
                else:
                    # If no items, clear the template item cells but keep it
                    fill_cell(template_item, 'Cantidad', "")
                    fill_cell(template_item, 'Unidades', "")
                    fill_cell(template_item, 'Producto', "(Sin artículos)")
                    fill_cell(template_item, 'Comentario', "")
                    
    # Save to a bytes buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
