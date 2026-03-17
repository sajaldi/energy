from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Q
from django.db import models
from .models import PresupuestoAnual, PartidaPresupuestaria, GastoEjecutado, ItemPresupuesto, PresupuestoAgrupado
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from datetime import datetime

@login_required
def cronograma_presupuesto(request, pk=None):
    if pk:
        presupuesto = get_object_or_404(PresupuestoAnual, pk=pk)
    else:
        presupuesto = PresupuestoAnual.objects.filter(anio=datetime.now().year).first()
        if not presupuesto:
            presupuesto = PresupuestoAnual.objects.order_by('-anio').first()
    
    if not presupuesto:
        return render(request, 'presupuestos/cronograma.html', {'error': 'No hay presupuestos configurados.'})

    data = _get_cronograma_data([presupuesto])
    
    context = {
        'presupuesto': presupuesto,
        'partidas_data': data['presupuestos_data'][0]['partidas'] if data['presupuestos_data'] else [],
        'meses_nombres': data['meses_nombres'],
        'global_proyectado_mes': data['global_proyectado_mes'],
        'global_ejecutado_mes': data['global_ejecutado_mes'],
        'total_general_proyectado': data['total_general_proyectado'],
        'total_general_ejecutado': data['total_general_ejecutado'],
    }

    return render(request, 'presupuestos/cronograma.html', context)

@login_required
def cronograma_grupal(request, pk):
    grupo = get_object_or_404(PresupuestoAgrupado, pk=pk)
    presupuestos = grupo.presupuestos.all()
    
    if not presupuestos:
        return render(request, 'presupuestos/cronograma_grupal.html', {
            'grupo': grupo,
            'error': 'Este grupo no tiene presupuestos vinculados.'
        })

    data = _get_cronograma_data(presupuestos)
    
    context = {
        'grupo': grupo,
        'presupuestos_data': data['presupuestos_data'],
        'meses_nombres': data['meses_nombres'],
        'global_proyectado_mes': data['global_proyectado_mes'],
        'global_ejecutado_mes': data['global_ejecutado_mes'],
        'total_general_proyectado': data['total_general_proyectado'],
        'total_general_ejecutado': data['total_general_ejecutado'],
    }

    return render(request, 'presupuestos/cronograma_grupal.html', context)


def _get_cronograma_data(presupuestos_list):
    """
    Agrega datos de uno o varios presupuestos.
    Retorna datos estructurados por presupuesto.
    Incluye soporte para sub-ítems.
    """
    meses_nombres = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    global_proyectado_mes = [0.0] * 12
    global_ejecutado_mes = [0.0] * 12
    presupuestos_data = []

    from .models import ItemSolicitudPago
    
    # Pre-cargar todos los pagos de los presupuestos involucrados con estatus PAGADO
    pagos_mapeo = {}
    pagos_qs = ItemSolicitudPago.objects.filter(
        estatus='PAGADO'
    ).filter(
        Q(requisicion__partida__presupuesto_anual__in=presupuestos_list) |
        Q(requisicion__item_presupuesto__partida__presupuesto_anual__in=presupuestos_list)
    ).select_related('requisicion', 'solicitud').distinct()
    
    for p_item in pagos_qs:
        it_id = p_item.requisicion.item_presupuesto_id
        if it_id:
            if it_id not in pagos_mapeo:
                pagos_mapeo[it_id] = [0.0] * 12
            if p_item.solicitud.fecha_solicitud:
                mes = p_item.solicitud.fecha_solicitud.month
                pagos_mapeo[it_id][mes-1] += float(p_item.monto_solicitado)

    for presupuesto in presupuestos_list:
        partidas = presupuesto.partidas.select_related('disciplina').prefetch_related(
            'items', 
            'items__detalles', 
            'items__subitems',
            'gastos'
        ).all()

        partidas_desglose = []
        p_total_proyectado_mensual = [0.0] * 12
        p_total_ejecutado_mensual = [0.0] * 12

        for p in partidas:
            p_disc_nombre = p.disciplina.nombre if p.disciplina else (p.descripcion or "Otros")
            
            # Ejecución de la partida
            ejecucion_partida = [0.0] * 12
            for gasto in p.gastos.all():
                m_idx = gasto.fecha.month - 1
                ejecucion_partida[m_idx] += float(gasto.monto)
                p_total_ejecutado_mensual[m_idx] += float(gasto.monto)
                global_ejecutado_mes[m_idx] += float(gasto.monto)

            # Ítems (solo nivel superior)
            items_tree = []
            proyeccion_partida = [0.0] * 12
            
            # Objetos de items de esta partida
            partida_items = list(p.items.all())
            top_items = [i for i in partida_items if not i.parent_id]
            
            for item in top_items:
                item_data = _get_item_recursive_data(item, partida_items, pagos_mapeo)
                items_tree.append(item_data)
                
                for i in range(12):
                    proyeccion_partida[i] += item_data['proyeccion'][i]
                    p_total_proyectado_mensual[i] += item_data['proyeccion'][i]
                    global_proyectado_mes[i] += item_data['proyeccion'][i]
                    # La ejecución global ya se suma desde gastos (GastoEjecutado)
                    # Pero aquí podríamos agregar la ejecución por ítem si fuera necesario.
                    # Por ahora el usuario pidió una línea debajo del ítem para trazabilidad.

            partidas_desglose.append({
                'partida': p,
                'disciplina': p_disc_nombre,
                'items': items_tree,
                'ejecucion_mensual': ejecucion_partida,
                'proyeccion_total_mensual': proyeccion_partida,
                'total_proyectado': sum(proyeccion_partida),
                'total_ejecutado': sum(ejecucion_partida),
                'gid': f"disc-{len(presupuestos_data) + 1}-{len(partidas_desglose) + 1}"
            })

        # Ordenar partidas por disciplina
        partidas_desglose.sort(key=lambda x: x['disciplina'])

        presupuestos_data.append({
            'presupuesto': presupuesto,
            'partidas': partidas_desglose,
            'total_mensual_proyectado': p_total_proyectado_mensual,
            'total_mensual_ejecutado': p_total_ejecutado_mensual,
            'total_anual_proyectado': sum(p_total_proyectado_mensual),
            'total_anual_ejecutado': sum(p_total_ejecutado_mensual),
            'gid': f"budget-{len(presupuestos_data) + 1}"
        })

    return {
        'presupuestos_data': presupuestos_data,
        'meses_nombres': meses_nombres,
        'global_proyectado_mes': global_proyectado_mes,
        'global_ejecutado_mes': global_ejecutado_mes,
        'total_general_proyectado': sum(global_proyectado_mes),
        'total_general_ejecutado': sum(global_ejecutado_mes),
    }

def _get_item_recursive_data(item, all_items, pagos_mapeo):
    """
    Obtiene datos de un ítem y sus sub-ítems recursivamente del cache 'all_items'.
    """
    proyeccion = [0.0] * 12
    for detalle in item.detalles.all():
        if 1 <= detalle.mes <= 12:
            proyeccion[detalle.mes - 1] += float(detalle.monto)
    
    # Obtener ejecución (pagos) para este ítem
    ejecucion = list(pagos_mapeo.get(item.id, [0.0] * 12))
    
    subitems_data = []
    # Buscar subitems en la lista precargada
    item_subitems = [i for i in all_items if i.parent_id == item.id]
    
    for subitem in item_subitems:
        sub_data = _get_item_recursive_data(subitem, all_items, pagos_mapeo)
        subitems_data.append(sub_data)
        for i in range(12):
            proyeccion[i] += sub_data['proyeccion'][i]
            ejecucion[i] += sub_data['ejecucion'][i]

    return {
        'id': item.id,
        'concepto': item.concepto,
        'proyeccion': proyeccion,
        'ejecucion': ejecucion,
        'total_anual': sum(proyeccion),
        'total_ejecutado_anual': sum(ejecucion),
        'subitems': subitems_data
    }

@login_required
def exportar_cronograma_excel(request, pk):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    presupuesto = get_object_or_404(PresupuestoAnual, pk=pk)
    data = _get_cronograma_data([presupuesto])
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Cronograma {presupuesto.anio}"
    
    # Estilos
    header_font = Font(bold=True, size=12, color="FFFFFF")
    header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")
    sub_header_font = Font(bold=True, size=11, color="000000")
    sub_header_fill = PatternFill(start_color="f1f5f9", end_color="f1f5f9", fill_type="solid")
    
    # 1. Título General
    ws['A1'] = f"PRESUPUESTO: {presupuesto.nombre} ({presupuesto.anio})"
    ws['A1'].font = Font(bold=True, size=14)
    ws.merge_cells('A1:O1')
    
    # 2. Encabezados de Tabla
    headers = ["Disciplina / Item"] + data['meses_nombres'] + ["TOTAL", "EJECUTADO"]
    ws.append([]) # Espacio
    ws.append(headers)
    
    # Aplicar estilo al encabezado
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        
        # Ajustar ancho columnas
        if col_num == 1:
            ws.column_dimensions[get_column_letter(col_num)].width = 40
        else:
            ws.column_dimensions[get_column_letter(col_num)].width = 15

    # 3. Datos
    current_row = 4
    # Obtener las partidas del primer (y único) presupuesto
    partidas_list = data['presupuestos_data'][0]['partidas'] if data['presupuestos_data'] else []
    
    for pd in partidas_list:
        # Fila Partida
        ws.cell(row=current_row, column=1, value=pd['disciplina']).font = sub_header_font
        ws.cell(row=current_row, column=1).fill = sub_header_fill
        
        for m_idx, val in enumerate(pd['proyeccion_total_mensual']):
            c = ws.cell(row=current_row, column=m_idx + 2, value=val)
            c.number_format = '#,##0'
            c.font = Font(bold=True)
            c.fill = sub_header_fill
            
        # Total Partida
        c_total = ws.cell(row=current_row, column=14, value=pd['total_proyectado'])
        c_total.number_format = '#,##0'
        c_total.font = Font(bold=True)
        c_total.fill = sub_header_fill
        
        current_row += 1
        
        # Filas Items
        for item in pd['items']:
            current_row += 1
            
            # Fila Pagado del Item (Trazabilidad)
            ws.cell(row=current_row, column=1, value=f"      (Pagado)").font = Font(italic=True, size=9, color="3b82f6")
            
            for m_idx, val in enumerate(item['ejecucion']):
                c = ws.cell(row=current_row, column=m_idx + 2, value=val if val > 0 else "")
                c.number_format = '#,##0'
                c.font = Font(italic=True, size=9, color="3b82f6")
                
            c_annual_exec = ws.cell(row=current_row, column=14, value=item['total_ejecutado_anual'])
            c_annual_exec.number_format = '#,##0'
            c_annual_exec.font = Font(italic=True, size=9, color="3b82f6", bold=True)
            
            current_row += 1

    # 4. Totales Finales
    current_row += 1
    ws.cell(row=current_row, column=1, value="TOTAL MENSUAL").font = header_font
    ws.cell(row=current_row, column=1).fill = header_fill
    
    for m_idx, val in enumerate(data['global_proyectado_mes']):
        c = ws.cell(row=current_row, column=m_idx + 2, value=val)
        c.font = header_font
        c.fill = header_fill
        c.number_format = '#,##0'
        
    c_grand = ws.cell(row=current_row, column=14, value=data['total_general_proyectado'])
    c_grand.font = header_font
    c_grand.fill = header_fill
    c_grand.number_format = '#,##0'

    # Response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Presupuesto_{presupuesto.anio}.xlsx'
    
    wb.save(response)
    return response

@login_required
def exportar_cronograma_pdf(request, pk):
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    from django.http import HttpResponse

    presupuesto = get_object_or_404(PresupuestoAnual, pk=pk)
    data = _get_cronograma_data([presupuesto])
    
    context = {
        'presupuesto': presupuesto,
        'partidas_data': data['presupuestos_data'][0]['partidas'] if data['presupuestos_data'] else [],
        'meses_nombres': data['meses_nombres'],
        'global_proyectado_mes': data['global_proyectado_mes'],
        'global_ejecutado_mes': data['global_ejecutado_mes'],
        'total_general_proyectado': data['total_general_proyectado'],
        'total_general_ejecutado': data['total_general_ejecutado'],
    }
    
    template_path = 'presupuestos/cronograma_pdf.html'
    template = get_template(template_path)
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Presupuesto_{presupuesto.anio}.pdf"'
    
    pisa_status = pisa.CreatePDF(
       html, dest=response
    )
    
    if pisa_status.err:
       return HttpResponse('Error creating PDF', status=500)
       
    return response

@login_required
def exportar_cronograma_grupal_excel(request, pk):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    grupo = get_object_or_404(PresupuestoAgrupado, pk=pk)
    presupuestos = grupo.presupuestos.all()

    if not presupuestos:
        return HttpResponse('El grupo no tiene presupuestos.', status=400)

    data = _get_cronograma_data(presupuestos)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Análisis Grupal"

    # Estilos
    header_font = Font(bold=True, size=12, color="FFFFFF")
    header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")
    budget_font = Font(bold=True, size=11, color="FFFFFF")
    budget_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    disciplina_font = Font(bold=True, size=11)
    disciplina_fill = PatternFill(start_color="f1f5f9", end_color="f1f5f9", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # 1. Título General
    ws['A1'] = f"ANÁLISIS GRUPAL: {grupo.nombre}"
    ws['A1'].font = Font(bold=True, size=14)
    ws.merge_cells('A1:O1')

    # 2. Totales Generales
    ws['A3'] = "TOTAL PROYECTADO:"
    ws['A3'].font = Font(bold=True)
    ws['B3'] = data['total_general_proyectado']
    ws['B3'].number_format = '#,##0.00'

    ws['A4'] = "TOTAL EJECUTADO:"
    ws['A4'].font = Font(bold=True)
    ws['B4'] = data['total_general_ejecutado']
    ws['B4'].number_format = '#,##0.00'

    if data['total_general_proyectado'] > 0:
        eficiencia = (data['total_general_ejecutado'] / data['total_general_proyectado']) * 100
        ws['A5'] = "EFICIENCIA:"
        ws['A5'].font = Font(bold=True)
        ws['B5'] = f"{eficiencia:.1f}%"
        ws['B5'].number_format = '0.0%'

    # 3. Encabezados de Tabla
    headers = ["Jerarquía"] + data['meses_nombres'] + ["TOTAL", "EJECUTADO"]
    ws.append([])  # Espacio
    ws.append(headers)

    # Aplicar estilo al encabezado
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=7, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

        # Ajustar ancho columnas
        if col_num == 1:
            ws.column_dimensions[get_column_letter(col_num)].width = 40
        else:
            ws.column_dimensions[get_column_letter(col_num)].width = 14

    # 4. Datos
    current_row = 8

    # Totales mensuales agrupados (fila principal)
    ws.cell(row=current_row, column=1, value="TOTAL MENSUAL AGRUPADO").font = budget_font
    ws.cell(row=current_row, column=1).fill = budget_fill
    ws.cell(row=current_row, column=1).border = thin_border

    for m_idx, val in enumerate(data['global_proyectado_mes']):
        c = ws.cell(row=current_row, column=m_idx + 2, value=val)
        c.number_format = '#,##0'
        c.font = budget_font
        c.fill = budget_fill
        c.alignment = Alignment(horizontal='right')
        c.border = thin_border

    c_total = ws.cell(row=current_row, column=14, value=data['total_general_proyectado'])
    c_total.number_format = '#,##0'
    c_total.font = budget_font
    c_total.fill = budget_fill
    c_total.border = thin_border

    c_ejec = ws.cell(row=current_row, column=15, value=data['total_general_ejecutado'])
    c_ejec.number_format = '#,##0'
    c_ejec.font = budget_font
    c_ejec.fill = budget_fill
    c_ejec.border = thin_border

    current_row += 1

    # Por cada presupuesto
    for bd in data['presupuestos_data']:
        # Fila Presupuesto
        ws.cell(row=current_row, column=1, value=bd['presupuesto'].nombre).font = budget_font
        ws.cell(row=current_row, column=1).fill = budget_fill
        ws.cell(row=current_row, column=1).border = thin_border

        for m_idx, val in enumerate(bd['total_mensual_proyectado']):
            c = ws.cell(row=current_row, column=m_idx + 2, value=val if val > 0 else 0)
            c.number_format = '#,##0'
            c.font = budget_font
            c.fill = budget_fill
            c.alignment = Alignment(horizontal='right')
            c.border = thin_border

        c_total = ws.cell(row=current_row, column=14, value=bd['total_anual_proyectado'])
        c_total.number_format = '#,##0'
        c_total.font = budget_font
        c_total.fill = budget_fill
        c_total.border = thin_border

        c_ejec = ws.cell(row=current_row, column=15, value=bd['total_anual_ejecutado'])
        c_ejec.number_format = '#,##0'
        c_ejec.font = budget_font
        c_ejec.fill = budget_fill
        c_ejec.border = thin_border

        current_row += 1

        # Por cada partida (disciplina)
        for pd in bd['partidas']:
            # Fila Disciplina
            ws.cell(row=current_row, column=1, value=pd['disciplina']).font = disciplina_font
            ws.cell(row=current_row, column=1).fill = disciplina_fill
            ws.cell(row=current_row, column=1).border = thin_border

            for m_idx, val in enumerate(pd['proyeccion_total_mensual']):
                c = ws.cell(row=current_row, column=m_idx + 2, value=val if val > 0 else 0)
                c.number_format = '#,##0'
                c.font = disciplina_font
                c.fill = disciplina_fill
                c.alignment = Alignment(horizontal='right')
                c.border = thin_border

            c_total = ws.cell(row=current_row, column=14, value=pd['total_proyectado'])
            c_total.number_format = '#,##0'
            c_total.font = disciplina_font
            c_total.fill = disciplina_fill
            c_total.border = thin_border

            c_ejec = ws.cell(row=current_row, column=15, value=pd['total_ejecutado'])
            c_ejec.number_format = '#,##0'
            c_ejec.font = disciplina_font
            c_ejec.fill = disciplina_fill
            c_ejec.border = thin_border

            current_row += 1

            # Items
            for item in pd['items']:
                ws.cell(row=current_row, column=1, value=f"   {item['concepto']}")
                ws.cell(row=current_row, column=1).border = thin_border

                for m_idx, val in enumerate(item['proyeccion']):
                    c = ws.cell(row=current_row, column=m_idx + 2, value=val if val > 0 else 0)
                    c.number_format = '#,##0'
                    c.alignment = Alignment(horizontal='right')
                    c.border = thin_border

                c_annual = ws.cell(row=current_row, column=14, value=item['total_anual'])
                c_annual.number_format = '#,##0'
                c_annual.border = thin_border

                c_ejec = ws.cell(row=current_row, column=15, value=item.get('total_ejecutado_anual', 0))
                c_ejec.number_format = '#,##0'
                c_ejec.border = thin_border

                current_row += 1
                
                # Fila Pagado para este Item
                ws.cell(row=current_row, column=1, value=f"      Pagado").font = Font(italic=True, size=9, color="3b82f6")
                ws.cell(row=current_row, column=1).border = thin_border
                
                for m_idx, pval in enumerate(item['ejecucion']):
                    c = ws.cell(row=current_row, column=m_idx + 2, value=pval if pval > 0 else 0)
                    c.number_format = '#,##0'
                    c.font = Font(italic=True, size=9, color="3b82f6")
                    c.border = thin_border
                    
                c_total_exec = ws.cell(row=current_row, column=14, value=item['total_ejecutado_anual'])
                c_total_exec.number_format = '#,##0'
                c_total_exec.font = Font(italic=True, size=9, color="3b82f6", bold=True)
                c_total_exec.border = thin_border
                
                ws.cell(row=current_row, column=15, value=item['total_ejecutado_anual']).border = thin_border
                
                current_row += 1

    # Ajustar anchos de columnas adicionales
    ws.column_dimensions['N'].width = 16
    ws.column_dimensions['O'].width = 16

    # Response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Analisis_Grupal_{grupo.nombre.replace(' ', '_')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response

@login_required
def exportar_cronograma_grupal_excel_pivot(request, pk):
    """
    Exporta los datos en formato plano para tabla pivote.
    Estructura: Presupuesto | Disciplina | Item | Concepto | Mes | Proyectado | Ejecutado
    """
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    grupo = get_object_or_404(PresupuestoAgrupado, pk=pk)
    presupuestos = grupo.presupuestos.all()

    if not presupuestos:
        return HttpResponse('El grupo no tiene presupuestos.', status=400)

    data = _get_cronograma_data(presupuestos)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Datos Pivote"

    # Encabezados
    headers = ["Presupuesto", "Disciplina", "Item", "Concepto", "Mes", "Proyectado", "Ejecutado"]
    ws.append(headers)

    # Estilo encabezado
    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    # Ancho columnas
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 40
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15

    meses_nombres = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                     'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    # Datos - por cada presupuesto
    for bd in data['presupuestos_data']:
        presupuesto_nombre = bd['presupuesto'].nombre
        presupuesto_ejecutado = bd['total_anual_ejecutado']

        # Por cada partida (disciplina)
        for pd in bd['partidas']:
            disciplina = pd['disciplina']
            partida_proyeccion = pd['proyeccion_total_mensual']
            partida_ejecutado = pd['total_ejecutado']

            # Fila de disciplina (sin item)
            for m_idx, mes_nombre in enumerate(meses_nombres):
                ws.append([
                    presupuesto_nombre,
                    disciplina,
                    "",
                    f"TOTAL {disciplina.upper()}",
                    mes_nombre,
                    partida_proyeccion[m_idx] if partida_proyeccion[m_idx] > 0 else 0,
                    0  # La ejecución se muestra a nivel de item, no de partida
                ])

            # Por cada item
            for item in pd['items']:
                item_concepto = item['concepto']
                item_proyeccion = item['proyeccion']
                item_ejecutado = item.get('total_ejecutado', 0)

                for m_idx, mes_nombre in enumerate(meses_nombres):
                    ws.append([
                        presupuesto_nombre,
                        disciplina,
                        item.get('codigo', ''),
                        item_concepto,
                        mes_nombre,
                        item_proyeccion[m_idx] if item_proyeccion[m_idx] > 0 else 0,
                        0  # Ejecutado mensual no está en item_data, sería 0
                    ])

                # Fila de total anual del item
                ws.append([
                    presupuesto_nombre,
                    disciplina,
                    item.get('codigo', ''),
                    f"TOTAL {item_concepto}",
                    "ANUAL",
                    item['total_anual'],
                    item_ejecutado
                ])

    # Totales mensuales agrupados
    ws.append([])
    ws.append(["TOTALES AGRUPADOS", "", "", "", "", "", ""])
    total_row = ws.max_row + 1

    for m_idx, mes_nombre in enumerate(meses_nombres):
        ws.append([
            "",
            "",
            "",
            f"TOTAL {mes_nombre.upper()}",
            "",
            data['global_proyectado_mes'][m_idx],
            data['global_ejecutado_mes'][m_idx]
        ])

    # Total anual
    ws.append([
        "",
        "",
        "",
        "TOTAL GENERAL",
        "",
        data['total_general_proyectado'],
        data['total_general_ejecutado']
    ])

    # Response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Analisis_Grupal_Pivot_{grupo.nombre.replace(' ', '_')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response

@login_required
def exportar_cronograma_grupal_excel_pivot(request, pk):
    """
    Exporta cronograma grupal en formato plano para tabla pivote.
    Estructura: Presupuesto | Disciplina | Item | Concepto | Mes | Valor
    Una fila por cada mes con valor.
    """
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    grupo = get_object_or_404(PresupuestoAgrupado, pk=pk)
    presupuestos = grupo.presupuestos.all()

    if not presupuestos:
        return HttpResponse('El grupo no tiene presupuestos.', status=400)

    data = _get_cronograma_data(presupuestos)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Datos Pivote"

    # Estilos
    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # 1. Título
    ws['A1'] = f"ANÁLISIS GRUPAL: {grupo.nombre} - Datos para Pivote"
    ws['A1'].font = Font(bold=True, size=14)
    ws.merge_cells('A1:E1')

    # 2. Encabezados - formato plano (una fila por mes)
    headers = ["Presupuesto", "Disciplina", "Item", "Concepto", "Mes", "Valor"]
    ws.append([])  # Espacio
    ws.append(headers)

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 30
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 15

    # 3. Datos - formato plano (una fila por cada mes con valor)
    current_row = 4

    for bd in data['presupuestos_data']:
        presupuesto_nombre = bd['presupuesto'].nombre

        for pd in bd['partidas']:
            disciplina = pd['disciplina']

            # Items
            for item in pd['items']:
                item_id = item.get('id', '')
                concepto = item['concepto']

                # Una fila por cada mes
                for m_idx, val in enumerate(item['proyeccion']):
                    # Columna A: Presupuesto
                    ws.cell(row=current_row, column=1, value=presupuesto_nombre).border = thin_border

                    # Columna B: Disciplina
                    ws.cell(row=current_row, column=2, value=disciplina).border = thin_border

                    # Columna C: Item ID
                    ws.cell(row=current_row, column=3, value=str(item_id)).border = thin_border

                    # Columna D: Concepto
                    ws.cell(row=current_row, column=4, value=concepto).border = thin_border

                    # Columna E: Mes
                    ws.cell(row=current_row, column=5, value=data['meses_nombres'][m_idx]).border = thin_border

                    # Columna F: Valor (Proyectado)
                    c = ws.cell(row=current_row, column=6, value=val if val > 0 else 0)
                    c.number_format = '#,##0'
                    c.alignment = Alignment(horizontal='right')
                    c.border = thin_border
                    
                    # Columna G: Pagado (Ejecutado de Solicitudes)
                    pval = item['ejecucion'][m_idx]
                    c2 = ws.cell(row=current_row, column=7, value=pval if pval > 0 else 0)
                    c2.number_format = '#,##0'
                    c2.alignment = Alignment(horizontal='right')
                    c2.border = thin_border

                    current_row += 1

    # Response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Analisis_Grupal_{grupo.nombre.replace(' ', '_')}_Pivote.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response


@login_required
def api_update_monto_mensual(request):
    if request.method == "POST":
        import json
        from .models import DetallePeriodico, ItemPresupuesto
        from django.http import JsonResponse
        
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            mes = int(data.get('mes'))
            monto = float(data.get('monto')) # Permitir float
            
            # Buscar Item Padre
            item = ItemPresupuesto.objects.get(pk=item_id)
            
            # Buscar o Crear detalle 
            # (Aunque usualmente ya existe, si el usuario pone monto > 0 en un mes donde no habia, lo creamos)
            detalle, created = DetallePeriodico.objects.get_or_create(
                item=item,
                mes=mes,
                defaults={'monto': monto}
            )
            
            if not created:
                detalle.monto = monto
                detalle.save()
            
            # Si el monto es 0, podríamos optar por borrar el detalle para limpiar la BD, 
            # pero por ahora mantenerlo es más seguro para la integridad histórica.
            
            return JsonResponse({'status': 'ok', 'new_total': float(item.total_anual)})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@login_required
def api_create_item(request):
    if request.method == "POST":
        import json
        from .models import ItemPresupuesto, PartidaPresupuestaria
        from django.http import JsonResponse
        
        try:
            data = json.loads(request.body)
            partida_id = data.get('partida_id')
            concepto = data.get('concepto')
            
            if not concepto:
                return JsonResponse({'status': 'error', 'message': 'El concepto es obligatorio'}, status=400)
                
            partida = PartidaPresupuestaria.objects.get(pk=partida_id)
            
            # Crear Item con defaults manuales
            item = ItemPresupuesto.objects.create(
                partida=partida,
                concepto=concepto,
                frecuencia='MANUAL',
                es_recurrente=False
            )
            
            return JsonResponse({'status': 'ok', 'message': 'Item creado'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@login_required
def api_create_partida(request):
    if request.method == "POST":
        import json
        from .models import PartidaPresupuestaria, PresupuestoAnual
        from django.http import JsonResponse
        
        try:
            data = json.loads(request.body)
            presupuesto_id = data.get('presupuesto_id')
            nombre = data.get('nombre')
            
            if not nombre:
                return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'}, status=400)
                
            presupuesto = PresupuestoAnual.objects.get(pk=presupuesto_id)
            
            # Crear Partida genérica (Sin disciplina vinculada, usando descripcion)
            PartidaPresupuestaria.objects.create(
                presupuesto_anual=presupuesto,
                disciplina=None,
                descripcion=nombre,
                monto_proyectado=0 
            )
            
            return JsonResponse({'status': 'ok', 'message': 'Partida creada'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@login_required
def api_update_item(request):
    if request.method == "POST":
        import json
        from .models import ItemPresupuesto
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            concepto = data.get('concepto')
            
            if not item_id or not concepto:
                 return JsonResponse({'status': 'error', 'message': 'Faltan datos'}, status=400)

            item = get_object_or_404(ItemPresupuesto, pk=item_id)
            item.concepto = concepto
            item.save()
            
            return JsonResponse({'status': 'ok', 'message': 'Item actualizado'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@login_required
def api_delete_item(request):
    if request.method == "POST":
        import json
        from .models import ItemPresupuesto
        from django.http import JsonResponse
        
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            
            item = get_object_or_404(ItemPresupuesto, pk=item_id)
            item.delete()
            
            return JsonResponse({'status': 'ok', 'message': 'Item eliminado'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@login_required
def api_delete_partida(request):
    if request.method == "POST":
        import json
        from .models import PartidaPresupuestaria
        from django.http import JsonResponse
        
        try:
            data = json.loads(request.body)
            partida_id = data.get('partida_id')
            
            partida = get_object_or_404(PartidaPresupuestaria, pk=partida_id)
            
            # Opcional: Validar si tiene items o gastos antes de borrar
            # Por ahora permitimos borrar y Django manejará cascadas si las hay
            partida.delete()
            
            return JsonResponse({'status': 'ok', 'message': 'Partida eliminada'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@login_required
def exportar_cronograma_grupal_pdf(request, pk):
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    from django.http import HttpResponse

    grupo = get_object_or_404(PresupuestoAgrupado, pk=pk)
    presupuestos = grupo.presupuestos.all()
    
    if not presupuestos:
        return HttpResponse('El grupo no tiene presupuestos.', status=400)

    data = _get_cronograma_data(presupuestos)
    
    context = {
        'grupo': grupo,
        'presupuestos_data': data['presupuestos_data'],
        'meses_nombres': data['meses_nombres'],
        'global_proyectado_mes': data['global_proyectado_mes'],
        'global_ejecutado_mes': data['global_ejecutado_mes'],
        'total_general_proyectado': data['total_general_proyectado'],
        'total_general_ejecutado': data['total_general_ejecutado'],
    }
    
    template_path = 'presupuestos/cronograma_grupal_pdf.html'
    template = get_template(template_path)
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    filename = f"Analisis_Grupal_{grupo.nombre.replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    pisa_status = pisa.CreatePDF(
       html, dest=response
    )
    
    if pisa_status.err:
       return HttpResponse('Error creating PDF', status=500)
       
    return response


# ──────────────────────────────────────────────────
# REPEX Cronograma / Visualizador Interactivo
# ──────────────────────────────────────────────────

@login_required
def cronograma_repex(request, pk):
    from .models import REPEX
    repex = get_object_or_404(REPEX, pk=pk)
    data = _get_repex_cronograma_data(repex)

    # Vista detalle de activos
    items_detalle = []
    items_qs = repex.items.select_related(
        'activo', 'activo__modelo', 'activo__modelo__marca',
        'activo__modelo__categoria', 'activo__ubicacion', 'activo__familia',
        'modelo', 'modelo__marca', 'modelo__categoria'
    ).all()

    for item in items_qs:
        activo = item.activo
        if activo:
            # Item vinculado a un activo
            # Lógica para obtener el edificio raíz (Main Building)
            edificio_obj = activo.ubicacion
            if edificio_obj:
                # Subir hasta encontrar el nivel superior que sea de tipo EDIFICIO o Campus (root)
                # O simplemente el primer ancestro que sea 'EDIFICIO'
                visited = {edificio_obj.id}
                curr = edificio_obj
                found_edificio = edificio_obj if edificio_obj.tipo == 'EDIFICIO' else None
                
                # Buscamos el ancestro tipo EDIFICIO
                temp_curr = edificio_obj.padre
                while temp_curr:
                    if temp_curr.id in visited: break
                    visited.add(temp_curr.id)
                    if temp_curr.tipo == 'EDIFICIO':
                        found_edificio = temp_curr
                    temp_curr = temp_curr.padre
                
                if found_edificio:
                    nombre_edificio = found_edificio.nombre
                else:
                    # Si no hay tipo EDIFICIO, usamos la raíz de la jerarquía
                    nombre_edificio = edificio_obj.get_root().nombre
            else:
                nombre_edificio = '-'
            
            ruta_ubicacion = nombre_edificio
            ruta_categoria = ''
            if activo.modelo and activo.modelo.categoria:
                cat = activo.modelo.categoria
                path = [cat.nombre]
                curr = cat.padre
                visited = {cat.id}
                while curr:
                    if curr.id in visited:
                        break
                    visited.add(curr.id)
                    path.append(curr.nombre)
                    curr = curr.padre
                ruta_categoria = ' → '.join(reversed(path))
            else:
                ruta_categoria = '-'

            items_detalle.append({
                'id': item.id,
                'activo_nombre': activo.nombre,
                'codigo': activo.codigo_interno or '-',
                'marca': activo.modelo.marca.nombre if activo.modelo and activo.modelo.marca else '-',
                'modelo': activo.modelo.nombre if activo.modelo else '-',
                'ruta_ubicacion': ruta_ubicacion,
                'ruta_categoria': ruta_categoria,
                'familia': activo.familia.nombre if activo.familia else '-',
                'costo_reposicion': float(item.costo_reposicion or 0),
                'prioridad': item.prioridad,
                'es_manual': False,
                'cantidad': float(item.cantidad or 1),
                'unidades': item.unidades or '',
                'precio_unitario': float(item.precio_unitario or 0),
            })
        else:
            # Item manual sin activo
            modelo_str = '-'
            marca_str = '-'
            if item.modelo:
                modelo_str = item.modelo.nombre
                if hasattr(item.modelo, 'marca') and item.modelo.marca:
                    marca_str = item.modelo.marca.nombre

            ruta_categoria = item.categoria_manual
            if not ruta_categoria and item.modelo and item.modelo.categoria:
                cat = item.modelo.categoria
                path = [cat.nombre]
                curr = cat.padre
                visited = {cat.id}
                while curr:
                    if curr.id in visited: break
                    visited.add(curr.id)
                    path.append(curr.nombre)
                    curr = curr.padre
                ruta_categoria = ' → '.join(reversed(path))
            
            if not ruta_categoria:
                ruta_categoria = 'Sin Categoría'

            items_detalle.append({
                'id': item.id,
                'activo_nombre': item.nombre_item or 'Ítem manual',
                'codigo': '-',
                'marca': marca_str,
                'modelo': modelo_str,
                'ruta_ubicacion': item.ubicacion_manual or '-',
                'ruta_categoria': ruta_categoria,
                'familia': ruta_categoria,
                'costo_reposicion': float(item.costo_reposicion or 0),
                'prioridad': item.prioridad,
                'es_manual': True,
                'cantidad': float(item.cantidad or 1),
                'unidades': item.unidades or '',
                'precio_unitario': float(item.precio_unitario or 0),
            })

    # Agrupar por categoría y luego por edificio para vista jerárquica de 3 niveles
    from collections import OrderedDict
    hierarchical_dict = OrderedDict()
    resumen_dict = OrderedDict()

    for item in items_detalle:
        cat = item['ruta_categoria']
        building = item['ruta_ubicacion']
        item_id = item['id']

        # 1. Estructura para Detalle/Presupuesto (3 niveles)
        if cat not in hierarchical_dict:
            hierarchical_dict[cat] = {
                'nombre': cat, 
                'edificios': OrderedDict(), 
                'total': 0.0, 
                'count': 0
            }
        
        if building not in hierarchical_dict[cat]['edificios']:
            hierarchical_dict[cat]['edificios'][building] = {
                'nombre': building, 
                'items': [], 
                'total_edificio': 0.0
            }
        
        hierarchical_dict[cat]['edificios'][building]['items'].append(item)
        hierarchical_dict[cat]['edificios'][building]['total_edificio'] += item['costo_reposicion']
        hierarchical_dict[cat]['total'] += item['costo_reposicion']
        hierarchical_dict[cat]['count'] += 1

        # 2. Resumen por Modelo (existente)
        if cat not in resumen_dict:
            resumen_dict[cat] = {'nombre': cat, 'modelos': OrderedDict(), 'total': 0.0, 'total_cantidad': 0.0}
        
        modelo_key = f"{item['marca']} | {item['modelo']}"
        if modelo_key not in resumen_dict[cat]['modelos']:
            resumen_dict[cat]['modelos'][modelo_key] = {
                'marca': item['marca'],
                'modelo': item['modelo'],
                'cantidad': 0,
                'precio_unitario': item['precio_unitario'],
                'total': 0.0
            }
        
        m_data = resumen_dict[cat]['modelos'][modelo_key]
        m_data['cantidad'] += item['cantidad']
        m_data['total'] += item['costo_reposicion']
        resumen_dict[cat]['total'] += item['costo_reposicion']
        resumen_dict[cat]['total_cantidad'] += item['cantidad']

    # Convertir a listas para el template
    presupuesto_jerarquico = []
    for cat_name, c_data in hierarchical_dict.items():
        cat_item = {
            'nombre': cat_name,
            'total': c_data['total'],
            'count': c_data['count'],
            'edificios': []
        }
        for b_name, b_data in c_data['edificios'].items():
            cat_item['edificios'].append(b_data)
        presupuesto_jerarquico.append(cat_item)

    resumen_modelos = []
    for cat_name, r_data in resumen_dict.items():
        total_cat = r_data['total']
        cant_cat = r_data['total_cantidad']
        promedio_pu = total_cat / cant_cat if cant_cat > 0 else 0
        
        resumen_modelos.append({
            'nombre': cat_name,
            'modelos': list(r_data['modelos'].values()),
            'total': total_cat,
            'total_cantidad': cant_cat,
            'promedio_pu': promedio_pu
        })

    context = {
        'repex': repex,
        'familias_data': data['familias_data'],
        'anios_nombres': data['anios_nombres'],
        'total_anual': data['total_mensual'], # Renombrando key para template y vista
        'total_general': data['total_general'],
        'total_items': data['total_items'],
        'items_detalle': items_detalle,
        'presupuesto_jerarquico': presupuesto_jerarquico, # Nueva estructura 3 niveles
        'resumen_modelos': resumen_modelos,
    }
    return render(request, 'presupuestos/cronograma_repex.html', context)


@login_required
def exportar_repex_excel(request, pk):
    """Exporta el plan REPEX a Excel. Acepta ?vista=detalle|apu|cronograma para cambiar formato."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    from .models import REPEX
    from collections import OrderedDict

    repex = get_object_or_404(REPEX, pk=pk)
    vista = request.GET.get('vista', 'detalle')

    # Styles
    header_fill = PatternFill(start_color='3D5A80', end_color='3D5A80', fill_type='solid')
    header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    cat_fill = PatternFill(start_color='C8D8E8', end_color='C8D8E8', fill_type='solid')
    cat_font = Font(name='Calibri', bold=True, color='1E3A5F', size=11)
    item_font = Font(name='Calibri', size=10, color='333333')
    total_fill = PatternFill(start_color='2C4A6E', end_color='2C4A6E', fill_type='solid')
    total_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    money_fmt = '#,##0.00'
    thin_border = Border(bottom=Side(style='thin', color='C8CED8'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.sheet_properties.outlinePr.summaryBelow = False

    if vista == 'cronograma':
        # ── CRONOGRAMA MENSUAL (MATRIZ) ──
        ws.title = f"Cronograma REPEX {repex.anio}"
        data = _get_repex_cronograma_data(repex)
        
        # Title (Col A to Z, since 1+1+24 = 26)
        last_col = get_column_letter(26)
        ws.merge_cells(f'A1:{last_col}')
        ws['A1'].value = f"REPEX {repex.anio} — {repex.nombre} (Cronograma Mensual)"
        ws['A1'].font = Font(name='Calibri', bold=True, size=14, color='2C4A6E')
        ws.row_dimensions[1].height = 30
        ws.append([])

        # Headers
        headers = ['FAMILIA / ITEM', 'TOTAL'] + data['meses_nombres']
        ws.append(headers)
        hr = ws.max_row
        for col, _ in enumerate(headers, 1):
            cell = ws.cell(row=hr, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[hr].height = 25
        ws.column_dimensions['A'].width = 45
        ws.column_dimensions['B'].width = 15
        for col in range(3, 27):
            ws.column_dimensions[get_column_letter(col)].width = 10

        for fam in data['familias_data']:
            # Familia row
            row_data = [fam['familia_nombre'].upper(), fam['total']] + fam['mensual']
            ws.append(row_data)
            r_fam = ws.max_row
            for col in range(1, 27): # Changed from 15 to 27
                ws.cell(row=r_fam, column=col).fill = total_fill
                ws.cell(row=r_fam, column=col).font = total_font
                if col >= 2:
                    ws.cell(row=r_fam, column=col).number_format = money_fmt
            
            group_fam_start = ws.max_row + 1
            for cat in fam['categorias']:
                # Categoria Row
                row_cat = [cat['nombre'].upper(), cat['total']] + cat['mensual']
                ws.append(row_cat)
                r_cat = ws.max_row
                ws.cell(row=r_cat, column=1).alignment = Alignment(indent=2)
                for col in range(1, 27): # Changed from 15 to 27
                    ws.cell(row=r_cat, column=col).fill = cat_fill
                    ws.cell(row=r_cat, column=col).font = cat_font
                    if col >= 2:
                        ws.cell(row=r_cat, column=col).number_format = money_fmt
                
                group_cat_start = ws.max_row + 1
                for ub in cat['ubicaciones']:
                    # Ubicacion Row
                    row_ub = [ub['nombre'], ub['total']] + ub['mensual']
                    ws.append(row_ub)
                    r_ub = ws.max_row
                    ws.cell(row=r_ub, column=1).alignment = Alignment(indent=4)
                    for col in range(1, 27): # Changed from 15 to 27
                        ws.cell(row=r_ub, column=col).font = Font(name='Calibri', bold=True, size=10)
                        if col >= 2:
                            ws.cell(row=r_ub, column=col).number_format = money_fmt
                    
                    group_ub_start = ws.max_row + 1
                    for item in ub['items']:
                        row_item = [item['activo_nombre'], item['total']] + item['mensual']
                        ws.append(row_item)
                        ir = ws.max_row
                        ws.cell(row=ir, column=1).alignment = Alignment(indent=6)
                        for col in range(1, 27): # Changed from 15 to 27
                            ws.cell(row=ir, column=col).font = item_font
                            ws.cell(row=ir, column=col).border = thin_border
                            if col >= 2:
                                ws.cell(row=ir, column=col).number_format = money_fmt
                                ws.cell(row=ir, column=col).alignment = Alignment(horizontal='right')
                    
                    group_ub_end = ws.max_row
                    if group_ub_end >= group_ub_start:
                        ws.row_dimensions.group(group_ub_start, group_ub_end, outline_level=3, hidden=True)
                
                group_cat_end = ws.max_row
                if group_cat_end >= group_cat_start:
                    ws.row_dimensions.group(group_cat_start, group_cat_end, outline_level=2, hidden=True)
            
            group_fam_end = ws.max_row
            if group_fam_end >= group_fam_start:
                ws.row_dimensions.group(group_fam_start, group_fam_end, outline_level=1, hidden=True)

        # Totales mensuales
        ws.append([])
        total_row = ['TOTAL MENSUAL', data['total_general']] + data['total_mensual']
        ws.append(total_row)
        tr = ws.max_row
        for col in range(1, 27): # Changed from 15 to 27
            ws.cell(row=tr, column=col).fill = total_fill
            ws.cell(row=tr, column=col).font = total_font
            if col >= 2:
                ws.cell(row=tr, column=col).number_format = money_fmt

    else:
        # ── DETALLE / APU with 3-level hierarchy ──
        items_qs = repex.items.select_related(
            'activo', 'activo__modelo', 'activo__modelo__marca',
            'activo__modelo__categoria', 'activo__ubicacion', 'activo__familia',
            'modelo', 'modelo__marca', 'modelo__categoria'
        ).all()

        hierarchical_obj = OrderedDict()
        for item in items_qs:
            # Category name logic
            activo = item.activo
            cat_name = '-'
            if activo:
                if activo.modelo and activo.modelo.categoria:
                    cat = activo.modelo.categoria
                    path = [cat.nombre]
                    curr = cat.padre
                    visited = {cat.id}
                    while curr:
                        if curr.id in visited: break
                        visited.add(curr.id)
                        path.append(curr.nombre)
                        curr = curr.padre
                    cat_name = ' → '.join(reversed(path))
            else:
                cat_name = item.categoria_manual
                if not cat_name and item.modelo and item.modelo.categoria:
                    cat = item.modelo.categoria
                    path = [cat.nombre]
                    curr = cat.padre
                    visited = {cat.id}
                    while curr:
                        if curr.id in visited: break
                        visited.add(curr.id)
                        path.append(curr.nombre)
                        curr = curr.padre
                    cat_name = ' → '.join(reversed(path))
                
                if not cat_name:
                    cat_name = 'Sin Categoría'
            
            # Logic for Building grouping
            if activo and activo.ubicacion:
                edificio_obj = activo.ubicacion
                visited_ub = {edificio_obj.id}
                found_edificio = edificio_obj if edificio_obj.tipo == 'EDIFICIO' else None
                temp_curr = edificio_obj.padre
                while temp_curr:
                    if temp_curr.id in visited_ub: break
                    visited_ub.add(temp_curr.id)
                    if temp_curr.tipo == 'EDIFICIO':
                        found_edificio = temp_curr
                    temp_curr = temp_curr.padre
                
                building_name = found_edificio.nombre if found_edificio else edificio_obj.get_root().nombre
            else:
                building_name = item.ubicacion_manual or '-'
            
            if cat_name not in hierarchical_obj:
                hierarchical_obj[cat_name] = OrderedDict()
            
            if building_name not in hierarchical_obj[cat_name]:
                hierarchical_obj[cat_name][building_name] = {'items': [], 'total_edificio': 0.0}
            
            # Common metadata
            modelo_str = '-'
            marca_str = '-'
            if activo and activo.modelo:
                modelo_str = activo.modelo.nombre
                if activo.modelo.marca:
                    marca_str = activo.modelo.marca.nombre
            elif item.modelo:
                modelo_str = item.modelo.nombre
                if hasattr(item.modelo, 'marca') and item.modelo.marca:
                    marca_str = item.modelo.marca.nombre

            if vista == 'apu':
                val = {
                    'codigo': activo.codigo_interno if activo else '-',
                    'nombre': item.display_nombre,
                    'marca': marca_str,
                    'modelo': modelo_str,
                    'unidades': item.unidades or 'Unidad',
                    'cantidad': float(item.cantidad or 1),
                    'precio_unitario': float(item.precio_unitario or 0),
                    'costo': float(item.costo_reposicion or 0),
                }
            else:
                val = {
                    'codigo': activo.codigo_interno if activo else '-',
                    'nombre': item.display_nombre,
                    'marca': marca_str,
                    'modelo': modelo_str,
                    'ubicacion': building_name,
                    'prioridad': item.prioridad,
                    'costo': float(item.costo_reposicion or 0),
                }
            
            hierarchical_obj[cat_name][building_name]['items'].append(val)
            hierarchical_obj[cat_name][building_name]['total_edificio'] += val['costo']

        ws.merge_cells('A1:H1')
        ws['A1'].value = f"REPEX {repex.anio} — {repex.nombre}"
        ws['A1'].font = Font(name='Calibri', bold=True, size=14, color='2C4A6E')
        ws.row_dimensions[1].height = 30
        ws.append([])

        if vista == 'apu':
            ws.title = "Presupuesto"
            headers = ['CODIGO', 'UBICACION', 'DESCRIPCION', 'MODELO', 'UNIDAD', 'CNTD', 'P.U.', 'IMPORTE']
            col_widths = [12, 30, 40, 20, 12, 10, 16, 18]
        else:
            ws.title = "Detalle"
            headers = ['Código', 'Activo', 'Marca', 'Modelo', 'Ruta Ubicación', 'Categoría', 'Prioridad', 'Costo Reposición']
            col_widths = [14, 30, 16, 18, 35, 30, 12, 18]

        ws.append(headers)
        hr = ws.max_row
        for col_idx in range(1, 9):
            cell = ws.cell(row=hr, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[hr].height = 28
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        cat_idx = 0
        total_repex = 0.0
        for cat_name, edificiions_dict in hierarchical_obj.items():
            cat_idx += 1
            cat_total = sum(e['total_edificio'] for e in edificiions_dict.values())
            total_repex += cat_total
            
            # Level 1 Heading
            ws.append([f'{cat_idx}.', '', cat_name.upper(), '', '', '', '', cat_total])
            r = ws.max_row
            ws.merge_cells(f'C{r}:G{r}')
            for col in range(1, 9):
                ws.cell(row=r, column=col).fill = total_fill
                ws.cell(row=r, column=col).font = total_font
            ws.cell(row=r, column=8).number_format = money_fmt
            
            group_1_start = ws.max_row + 1
            
            b_idx = 0
            for b_name, b_data in edificiions_dict.items():
                b_idx += 1
                # Level 2 Heading
                ws.append([f'{cat_idx}.{b_idx}', b_name, '', '', '', '', '', b_data['total_edificio']])
                br = ws.max_row
                ws.merge_cells(f'B{br}:G{br}')
                for col in range(1, 9):
                    ws.cell(row=br, column=col).fill = cat_fill
                    ws.cell(row=br, column=col).font = cat_font
                ws.cell(row=br, column=8).number_format = money_fmt
                ws.cell(row=br, column=1).alignment = Alignment(horizontal='right')
                
                group_2_start = ws.max_row + 1
                for i_idx, item in enumerate(b_data['items'], 1):
                    # Level 3 Data
                    if vista == 'apu':
                        row = [f'{cat_idx}.{b_idx}.{i_idx}', item['codigo'], item['nombre'], item['modelo'], item['unidades'], item['cantidad'], item['precio_unitario'], item['costo']]
                    else:
                        row = [f'{cat_idx}.{b_idx}.{i_idx}', item['nombre'], item['marca'], item['modelo'], item['ubicacion'], cat_name, item['prioridad'], item['costo']]
                    
                    ws.append(row)
                    ir = ws.max_row
                    for col in range(1, 9):
                        ws.cell(row=ir, column=col).font = item_font
                        ws.cell(row=ir, column=col).border = thin_border
                    
                    if vista == 'apu':
                        ws.cell(row=ir, column=6).number_format = money_fmt # CNTD
                        ws.cell(row=ir, column=7).number_format = money_fmt # P.U.
                    ws.cell(row=ir, column=8).number_format = money_fmt # IMPORTE
                    ws.cell(row=ir, column=1).alignment = Alignment(horizontal='right')

                group_2_end = ws.max_row
                if group_2_end >= group_2_start:
                    ws.row_dimensions.group(group_2_start, group_2_end, outline_level=2, hidden=False)

            group_1_end = ws.max_row
            if group_1_end >= group_1_start:
                ws.row_dimensions.group(group_1_start, group_1_end, outline_level=1, hidden=False)

        ws.append([])
        ws.append(['', '', '', '', '', '', 'TOTAL GENERAL', total_repex])
        r = ws.max_row
        for col in range(1, 9):
            ws.cell(row=r, column=col).fill = total_fill
            ws.cell(row=r, column=col).font = total_font
        ws.cell(row=r, column=8).number_format = money_fmt

    # Response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    vista_labels = {'cronograma': 'Cronograma', 'apu': 'Presupuesto', 'detalle': 'Detalle'}
    filename = f"REPEX_{repex.anio}_{vista_labels.get(vista, 'Export')}_{repex.nombre.replace(' ', '_')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    wb.save(response)
    return response


def _get_repex_cronograma_data(repex):
    """
    Genera datos matriciales de un plan REPEX agrupados por Familia del Activo.
    Timespan de 5 años: 2026, 2027, 2028, 2029, 2030.
    """
    anios_rango = [2026, 2027, 2028, 2029, 2030]
    anios_nombres = [str(a) for a in anios_rango]
    
    # Ampliamos el filtro para cubrir el rango de años solicitado
    items = repex.items.select_related('activo', 'activo__familia', 'modelo', 'modelo__categoria').filter(
        Q(fecha_proyectada__year__in=anios_rango) | Q(fecha_proyectada__isnull=True)
    ).all()

    # Agrupar por Familia > Categoría > Ubicación
    familias = {}
    for item in items:
        # 1. Familia
        if item.activo:
            familia_nombre = item.activo.familia.nombre if item.activo.familia else "Sin Familia"
            familia_id = item.activo.familia.id if item.activo.familia else 0
        else:
            if item.modelo and item.modelo.categoria:
                familia_nombre = item.modelo.categoria.nombre
                familia_id = item.modelo.categoria.id
            else:
                familia_nombre = item.categoria_manual or "Ítems Manuales"
                familia_id = -1
        
        fam_key = (familia_id, familia_nombre)
        if fam_key not in familias:
            familias[fam_key] = {
                'familia_nombre': familia_nombre,
                'familia_id': familia_id,
                'categorias': {},
                'mensual': [0.0] * 5, # Usamos 'mensual' pero ahora representa años
                'total': 0.0,
            }

        # 2. Categoría (Ruta completa o categoría principal)
        if item.activo and item.activo.modelo and item.activo.modelo.categoria:
            cat_nombre = item.activo.modelo.categoria.nombre
        elif item.modelo and item.modelo.categoria:
            cat_nombre = item.modelo.categoria.nombre
        else:
            cat_nombre = item.categoria_manual or "Sin Categoría"
        
        cat_key = cat_nombre
        if cat_key not in familias[fam_key]['categorias']:
            familias[fam_key]['categorias'][cat_key] = {
                'nombre': cat_nombre,
                'ubicaciones': {},
                'mensual': [0.0] * 5,
                'total': 0.0,
            }

        # 3. Ubicación
        if item.activo and item.activo.ubicacion:
            edificio_obj = item.activo.ubicacion
            visited_ub = {edificio_obj.id}
            found_edificio = edificio_obj if edificio_obj.tipo == 'EDIFICIO' else None
            temp_curr = edificio_obj.padre
            while temp_curr:
                if temp_curr.id in visited_ub: break
                visited_ub.add(temp_curr.id)
                if temp_curr.tipo == 'EDIFICIO':
                    found_edificio = temp_curr
                temp_curr = temp_curr.padre
            ubicacion_nombre = found_edificio.nombre if found_edificio else edificio_obj.get_root().nombre
        else:
            ubicacion_nombre = item.ubicacion_manual or "Sin Ubicación"

        ub_key = ubicacion_nombre
        if ub_key not in familias[fam_key]['categorias'][cat_key]['ubicaciones']:
            familias[fam_key]['categorias'][cat_key]['ubicaciones'][ub_key] = {
                'nombre': ubicacion_nombre,
                'items': [],
                'mensual': [0.0] * 5,
                'total': 0.0,
            }

        # 4. Determinar monto anual (horizonte 5 años)
        item_anual = [0.0] * 5
        costo = float(item.costo_reposicion or 0)
        anio_proyectado = None

        if item.fecha_proyectada:
            fp = item.fecha_proyectada
            if fp.year in anios_rango:
                anio_idx = anios_rango.index(fp.year)
                item_anual[anio_idx] = costo
                anio_proyectado = fp.year

        # Agregar Item
        familias[fam_key]['categorias'][cat_key]['ubicaciones'][ub_key]['items'].append({
            'id': item.id,
            'activo_nombre': item.display_nombre,
            'descripcion': item.descripcion or '',
            'prioridad': item.prioridad,
            'costo_reposicion': costo,
            'mensual': item_anual, # Seguimos llamando 'mensual' para no romper el template excesivamente
            'total': costo,
            'anio_proyectado': anio_proyectado,
        })

        # Acumular Subtotales
        for i in range(5):
            val = item_anual[i]
            familias[fam_key]['mensual'][i] += val
            familias[fam_key]['categorias'][cat_key]['mensual'][i] += val
            familias[fam_key]['categorias'][cat_key]['ubicaciones'][ub_key]['mensual'][i] += val
        
        familias[fam_key]['total'] += costo
        familias[fam_key]['categorias'][cat_key]['total'] += costo
        familias[fam_key]['categorias'][cat_key]['ubicaciones'][ub_key]['total'] += costo

    # Convertir a listas ordenadas
    familias_data = []
    for f_key in sorted(familias.keys(), key=lambda x: x[1]):
        f_val = familias[f_key]
        cats_list = []
        for c_key in sorted(f_val['categorias'].keys()):
            c_val = f_val['categorias'][c_key]
            ubs_list = []
            for u_key in sorted(c_val['ubicaciones'].keys()):
                ubs_list.append(c_val['ubicaciones'][u_key])
            c_val['ubicaciones'] = ubs_list
            cats_list.append(c_val)
        f_val['categorias'] = cats_list
        familias_data.append(f_val)

    # Totales globales
    total_anual = [0.0] * 5
    total_general = 0.0
    total_items = 0

    for fam in familias_data:
        # Contar items en todos los niveles
        for cat in fam['categorias']:
            for ub in cat['ubicaciones']:
                total_items += len(ub['items'])
        
        for i in range(5):
            total_anual[i] += fam['mensual'][i]
        total_general += fam['total']

    from datetime import datetime
    return {
        'familias_data': familias_data,
        'anios_nombres': anios_nombres,
        'total_mensual': total_anual, # Mantenemos el key total_mensual por retrocompatibilidad con openpyxl views/template u otra ref, pero arriba pasamos 'total_anual'
        'total_general': total_general,
        'total_items': total_items,
    }


@login_required
def api_update_repex_item(request):
    """Actualiza costo_reposicion y fecha_proyectada de un REPEXItem."""
    if request.method == "POST":
        import json
        from decimal import Decimal
        from .models import REPEXItem
        from django.http import JsonResponse
        from datetime import date

        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            mes = int(data.get('mes') or 0)
            monto = Decimal(str(data.get('monto', 0)))

            item = get_object_or_404(REPEXItem, pk=item_id)
            
            # Actualizar precio unitario si hay cantidad para que save() lo asuma correctamente
            if item.cantidad > 0:
                item.precio_unitario = monto / item.cantidad
            else:
                item.costo_reposicion = monto

            # El cronograma anual usa 5 años: 2026 (1), 2027 (2), 2028 (3), 2029 (4), 2030 (5)
            if monto > 0 and 1 <= mes <= 5:
                anios_rango = [2026, 2027, 2028, 2029, 2030]
                target_year = anios_rango[mes - 1]
                # Si el ítem ya tenía una fecha, intentamos preservar el mes
                current_month = item.fecha_proyectada.month if item.fecha_proyectada else 1
                item.fecha_proyectada = date(target_year, current_month, 1)
            elif monto == 0:
                item.fecha_proyectada = None
                item.precio_unitario = 0
                item.costo_reposicion = 0

            item.save()
            return JsonResponse({'status': 'ok', 'new_total': float(item.costo_reposicion)})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@login_required
def api_update_repex_item_apu(request):
    """Actualiza cantidad o precio_unitario de un REPEXItem."""
    if request.method == "POST":
        import json
        from decimal import Decimal
        from .models import REPEXItem
        from django.http import JsonResponse

        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            field = data.get('field')  # 'cantidad' o 'precio_unitario'
            value = Decimal(str(data.get('value', 0)))

            item = get_object_or_404(REPEXItem, pk=item_id)
            if field == 'cantidad':
                item.cantidad = value
            elif field == 'precio_unitario':
                item.precio_unitario = value
            else:
                return JsonResponse({'status': 'error', 'message': 'Campo inválido'}, status=400)

            item.save()  # El método save() recalcula costo_reposicion (Decimal * Decimal)
            return JsonResponse({
                'status': 'ok', 
                'new_total': float(item.costo_reposicion),
                'cantidad': float(item.cantidad),
                'precio_unitario': float(item.precio_unitario)
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@login_required
def api_add_repex_item(request):
    """Agrega un activo existente al plan REPEX."""
    if request.method == "POST":
        import json
        from .models import REPEX, REPEXItem
        from activos.models.activo import Activo
        from django.http import JsonResponse

        try:
            data = json.loads(request.body)
            repex_id = data.get('repex_id')
            activo_id = data.get('activo_id')
            costo = float(data.get('costo', 0))

            repex = get_object_or_404(REPEX, pk=repex_id)
            activo = get_object_or_404(Activo, pk=activo_id)

            # Si el costo no viene en el request (es 0), intentar usar el precio promedio del modelo
            if costo <= 0 and activo.modelo and activo.modelo.precio_promedio:
                costo = float(activo.modelo.precio_promedio)

            # Verificar que no exista ya
            if REPEXItem.objects.filter(repex=repex, activo=activo).exists():
                return JsonResponse({'status': 'error', 'message': 'Este activo ya está en el plan REPEX.'}, status=400)

            REPEXItem.objects.create(
                repex=repex,
                activo=activo,
                costo_reposicion=costo,
                costo_original=activo.costo or 0,
            )
            return JsonResponse({'status': 'ok', 'message': 'Activo agregado al plan'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@login_required
def api_delete_repex_item(request):
    """Elimina un item del plan REPEX."""
    if request.method == "POST":
        import json
        from .models import REPEXItem
        from django.http import JsonResponse

        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            item = get_object_or_404(REPEXItem, pk=item_id)
            item.delete()
            return JsonResponse({'status': 'ok', 'message': 'Ítem eliminado del plan'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@login_required
def api_search_activos(request):
    """Busca activos por nombre o código para el selector del modal REPEX."""
    from activos.models.activo import Activo
    from django.http import JsonResponse

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    activos = Activo.objects.filter(
        models.Q(nombre__icontains=q) | models.Q(codigo_interno__icontains=q)
    ).select_related('familia')[:20]

    results = [{
        'id': a.id,
        'text': f"{a.nombre} ({a.codigo_interno})",
        'familia': a.familia.nombre if a.familia else 'Sin Familia',
        'costo': float(a.costo or 0),
    } for a in activos]

    return JsonResponse({'results': results})


@login_required
def api_import_repex_items(request):
    """
    Importa items REPEX masivamente desde un archivo Excel.
    Columnas esperadas: Activo (codigo_interno), Costo (costo_reposicion).
    Activos duplicados dentro del mismo plan se omiten.
    """
    if request.method != "POST":
        from django.http import JsonResponse
        return JsonResponse({'status': 'error', 'message': 'Método inválido'}, status=405)

    import openpyxl
    from io import BytesIO
    from .models import REPEX, REPEXItem
    from activos.models.activo import Activo
    from django.http import JsonResponse

    try:
        repex_id = request.POST.get('repex_id')
        archivo = request.FILES.get('archivo')

        if not archivo:
            return JsonResponse({'status': 'error', 'message': 'No se envió ningún archivo.'}, status=400)

        repex = get_object_or_404(REPEX, pk=repex_id)

        # Leer Excel
        wb = openpyxl.load_workbook(BytesIO(archivo.read()), read_only=True, data_only=True)
        ws = wb.active

        # Obtener encabezados de la primera fila
        headers = [str(cell.value or '').strip().lower() for cell in next(ws.iter_rows(min_row=1, max_row=1))]

        # Buscar índices de las columnas
        col_activo = None
        col_costo = None
        for i, h in enumerate(headers):
            if h in ('activo', 'codigo', 'codigo_interno', 'código', 'código_interno'):
                col_activo = i
            if h in ('costo', 'costo_reposicion', 'costo reposicion', 'costo_reposición', 'precio', 'monto'):
                col_costo = i

        if col_activo is None:
            return JsonResponse({
                'status': 'error',
                'message': f'No se encontró la columna "Activo". Columnas encontradas: {", ".join(headers)}'
            }, status=400)

        if col_costo is None:
            return JsonResponse({
                'status': 'error',
                'message': f'No se encontró la columna "Costo". Columnas encontradas: {", ".join(headers)}'
            }, status=400)

        # Cargar activos existentes en el plan para detectar duplicados
        existing_activo_ids = set(
            REPEXItem.objects.filter(repex=repex).values_list('activo_id', flat=True)
        )

        imported = 0
        skipped = 0
        errors = []

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if row is None or all(c is None for c in row):
                continue

            codigo_raw = str(row[col_activo] or '').strip()
            costo_raw = row[col_costo]

            if not codigo_raw:
                continue

            # Limpiar código (quitar .0 si viene como float de Excel)
            if '.' in codigo_raw:
                try:
                    codigo_raw = str(int(float(codigo_raw)))
                except (ValueError, OverflowError):
                    pass

            # Buscar activo por código interno
            try:
                activo = Activo.objects.get(codigo_interno=codigo_raw)
            except Activo.DoesNotExist:
                errors.append(f"Fila {row_idx}: Activo '{codigo_raw}' no encontrado.")
                continue
            except Activo.MultipleObjectsReturned:
                errors.append(f"Fila {row_idx}: Múltiples activos con código '{codigo_raw}'.")
                continue

            # Verificar duplicado
            if activo.id in existing_activo_ids:
                skipped += 1
                continue

            # Parsear costo
            try:
                costo = float(costo_raw or 0)
            except (ValueError, TypeError):
                costo = 0

            REPEXItem.objects.create(
                repex=repex,
                activo=activo,
                costo_reposicion=costo,
                costo_original=activo.costo or 0,
            )
            existing_activo_ids.add(activo.id)
            imported += 1

        wb.close()

        summary = f"✅ {imported} importados"
        if skipped > 0:
            summary += f", ⏭ {skipped} omitidos (duplicados)"
        if errors:
            summary += f", ❌ {len(errors)} errores"

        return JsonResponse({
            'status': 'ok',
            'message': summary,
            'imported': imported,
            'skipped': skipped,
            'errors': errors[:20],  # Limitar a 20 errores
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def api_add_manual_repex_item(request):
    """Agrega un ítem manual al plan REPEX (sin activo vinculado)."""
    from .models import REPEXItem, REPEX
    from activos.models import Modelo
    import json

    try:
        data = json.loads(request.body)
        repex_id = data.get('repex_id')
        modelo_id = data.get('modelo_id')
        nombre = data.get('nombre_item', '').strip()
        ubicacion = data.get('ubicacion_manual', '').strip()
        categoria = data.get('categoria_manual', '').strip()
        unidades_val = data.get('unidades', '').strip()
        cantidad_val = data.get('cantidad', 1)
        precio_val = data.get('precio_unitario', 0)
        prioridad = data.get('prioridad', 'MEDIA')

        if not repex_id:
            return JsonResponse({'status': 'error', 'message': 'El ID del REPEX es requerido.'}, status=400)

        repex = REPEX.objects.get(pk=repex_id)
        
        modelo_obj = None
        if modelo_id:
            modelo_obj = Modelo.objects.filter(pk=modelo_id).first()
            if modelo_obj:
                if not nombre:
                    nombre = f"{modelo_obj.marca.nombre} {modelo_obj.nombre}" if hasattr(modelo_obj, 'marca') else modelo_obj.nombre
                
                if not categoria and hasattr(modelo_obj, 'categoria') and modelo_obj.categoria:
                    categoria = modelo_obj.categoria.nombre
                    
                if not unidades_val and hasattr(modelo_obj, 'unidad_medida') and modelo_obj.unidad_medida:
                    unidades_val = modelo_obj.unidad_medida.nombre

                if (not precio_val or float(precio_val) == 0) and modelo_obj.precio_promedio:
                    precio_val = float(modelo_obj.precio_promedio)

        if not nombre:
             return JsonResponse({'status': 'error', 'message': 'Nombre del ítem es requerido.'}, status=400)

        item = REPEXItem(
            repex=repex,
            activo=None,
            modelo=modelo_obj,
            nombre_item=nombre,
            ubicacion_manual=ubicacion,
            categoria_manual=categoria,
            unidades=unidades_val,
            cantidad=cantidad_val,
            precio_unitario=precio_val,
            prioridad=prioridad,
        )
        item.save()  # save() auto-calcula costo_reposicion

        return JsonResponse({
            'status': 'ok',
            'message': f'Ítem "{nombre}" agregado (${item.costo_reposicion:,.2f})',
            'item_id': item.id,
        })

    except REPEX.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Plan REPEX no encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def requisicion_documento_proxy(request, doc_id):
    from .models import DocumentoRequisicion
    from django.http import FileResponse, Http404
    import mimetypes
    
    doc = get_object_or_404(DocumentoRequisicion, id=doc_id)
    if not doc.archivo:
        raise Http404("Documento no tiene archivo")
        
    try:
        file_handle = doc.archivo.open("rb")
        content_type, _ = mimetypes.guess_type(doc.archivo.name)
        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = f"inline; filename=\"{doc.archivo.name.split('/')[-1]}\""
        # Cabeceras de seguridad
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response
    except Exception as e:
        raise Http404(f"Error al acceder al archivo: {str(e)}")
