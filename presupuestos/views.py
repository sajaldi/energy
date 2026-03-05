from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum
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
                item_data = _get_item_recursive_data(item, partida_items)
                items_tree.append(item_data)
                
                for i in range(12):
                    proyeccion_partida[i] += item_data['proyeccion'][i]
                    p_total_proyectado_mensual[i] += item_data['proyeccion'][i]
                    global_proyectado_mes[i] += item_data['proyeccion'][i]

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

def _get_item_recursive_data(item, all_items):
    """
    Obtiene datos de un ítem y sus sub-ítems recursivamente del cache 'all_items'.
    """
    proyeccion = [0.0] * 12
    for detalle in item.detalles.all():
        if 1 <= detalle.mes <= 12:
            proyeccion[detalle.mes - 1] += float(detalle.monto)
    
    subitems_data = []
    # Buscar subitems en la lista precargada
    item_subitems = [i for i in all_items if i.parent_id == item.id]
    
    for subitem in item_subitems:
        sub_data = _get_item_recursive_data(subitem, all_items)
        subitems_data.append(sub_data)
        for i in range(12):
            proyeccion[i] += sub_data['proyeccion'][i]

    return {
        'id': item.id,
        'concepto': item.concepto,
        'proyeccion': proyeccion,
        'total_anual': sum(proyeccion),
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
            ws.cell(row=current_row, column=1, value=f"   {item['concepto']}")
            
            for m_idx, val in enumerate(item['proyeccion']):
                c = ws.cell(row=current_row, column=m_idx + 2, value=val if val > 0 else "")
                c.number_format = '#,##0'
                
            c_annual = ws.cell(row=current_row, column=14, value=item['total_anual'])
            c_annual.number_format = '#,##0'
            
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

                c_ejec = ws.cell(row=current_row, column=15, value=item.get('total_ejecutado', 0))
                c_ejec.number_format = '#,##0'
                c_ejec.border = thin_border

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

                    # Columna F: Valor
                    c = ws.cell(row=current_row, column=6, value=val if val > 0 else 0)
                    c.number_format = '#,##0'
                    c.alignment = Alignment(horizontal='right')
                    c.border = thin_border

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
        'activo__modelo__categoria', 'activo__ubicacion', 'activo__familia'
    ).all()

    for item in items_qs:
        activo = item.activo
        if activo:
            # Item vinculado a un activo
            ruta_ubicacion = activo.ubicacion.ruta_completa if activo.ubicacion else '-'
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
            items_detalle.append({
                'id': item.id,
                'activo_nombre': item.nombre_item or 'Ítem manual',
                'codigo': '-',
                'marca': '-',
                'modelo': '-',
                'ruta_ubicacion': item.ubicacion_manual or '-',
                'ruta_categoria': item.categoria_manual or 'Sin Categoría',
                'familia': item.categoria_manual or 'Sin Categoría',
                'costo_reposicion': float(item.costo_reposicion or 0),
                'prioridad': item.prioridad,
                'es_manual': True,
                'cantidad': float(item.cantidad or 1),
                'unidades': item.unidades or '',
                'precio_unitario': float(item.precio_unitario or 0),
            })

    # Agrupar por categoría para vista colapsable
    from collections import OrderedDict
    categorias_dict = OrderedDict()
    for item in items_detalle:
        cat = item['ruta_categoria']
        if cat not in categorias_dict:
            categorias_dict[cat] = {'nombre': cat, 'items': [], 'total': 0.0, 'count': 0}
        categorias_dict[cat]['items'].append(item)
        categorias_dict[cat]['total'] += item['costo_reposicion']
        categorias_dict[cat]['count'] += 1
    categorias_detalle = list(categorias_dict.values())

    context = {
        'repex': repex,
        'familias_data': data['familias_data'],
        'meses_nombres': data['meses_nombres'],
        'total_mensual': data['total_mensual'],
        'total_general': data['total_general'],
        'total_items': data['total_items'],
        'items_detalle': items_detalle,
        'categorias_detalle': categorias_detalle,
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
        
        # Title
        ws.merge_cells(f'A1:{get_column_letter(14)}')
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
        for col in range(3, 15):
            ws.column_dimensions[get_column_letter(col)].width = 12

        for fam in data['familias_data']:
            # Familia row
            row_data = [fam['familia_nombre'].upper(), fam['total']] + fam['mensual']
            ws.append(row_data)
            r = ws.max_row
            for col in range(1, 15):
                ws.cell(row=r, column=col).fill = cat_fill
                ws.cell(row=r, column=col).font = cat_font
                if col >= 2:
                    ws.cell(row=r, column=col).number_format = money_fmt
            
            # Items
            group_start = ws.max_row + 1
            for item in fam['items']:
                row_data = [item['activo_nombre'], item['total']] + item['mensual']
                ws.append(row_data)
                ir = ws.max_row
                ws.cell(row=ir, column=1).alignment = Alignment(indent=2)
                for col in range(1, 15):
                    ws.cell(row=ir, column=col).font = item_font
                    ws.cell(row=ir, column=col).border = thin_border
                    if col >= 2:
                        ws.cell(row=ir, column=col).number_format = money_fmt
                        ws.cell(row=ir, column=col).alignment = Alignment(horizontal='right')

            group_end = ws.max_row
            if group_end >= group_start:
                ws.row_dimensions.group(group_start, group_end, outline_level=1, hidden=False)

        # Totales mensuales
        ws.append([])
        total_row = ['TOTAL MENSUAL', data['total_general']] + data['total_mensual']
        ws.append(total_row)
        tr = ws.max_row
        for col in range(1, 15):
            ws.cell(row=tr, column=col).fill = total_fill
            ws.cell(row=tr, column=col).font = total_font
            if col >= 2:
                ws.cell(row=tr, column=col).number_format = money_fmt

    elif vista == 'apu':
        # ── PRESUPUESTO / APU ──
        items_qs = repex.items.select_related(
            'activo', 'activo__modelo', 'activo__modelo__marca',
            'activo__modelo__categoria', 'activo__ubicacion', 'activo__familia'
        ).all()
        
        categorias = OrderedDict()
        for item in items_qs:
            activo = item.activo
            cat_name = '-'
            if activo:
                if activo.modelo and activo.modelo.categoria:
                    cat = activo.modelo.categoria
                    path = [cat.nombre]
                    curr = cat.padre
                    while curr:
                        path.append(curr.nombre)
                        curr = curr.padre
                    cat_name = ' → '.join(reversed(path))
            else:
                cat_name = item.categoria_manual or 'Sin Categoría'
            
            if cat_name not in categorias:
                categorias[cat_name] = {'items': [], 'total': 0.0}
            
            val = {
                'codigo': activo.codigo_interno if activo else '-',
                'nombre': item.display_nombre,
                'modelo': (activo.modelo.nombre if activo and activo.modelo else '-') if activo else '-',
                'ubicacion': (activo.ubicacion.ruta_completa if activo and activo.ubicacion else '-') if activo else (item.ubicacion_manual or '-'),
                'unidades': item.unidades or 'Unidad',
                'cantidad': float(item.cantidad or 1),
                'precio_unitario': float(item.precio_unitario or 0),
                'costo': float(item.costo_reposicion or 0),
            }
            categorias[cat_name]['items'].append(val)
            categorias[cat_name]['total'] += val['costo']

        ws.title = f"Presupuesto REPEX {repex.anio}"
        apu_header_fill = PatternFill(start_color='6B94B8', end_color='6B94B8', fill_type='solid')

        ws.merge_cells('A1:H1')
        ws['A1'].value = f"REPEX {repex.anio} — {repex.nombre}"
        ws['A1'].font = Font(name='Calibri', bold=True, size=14, color='2C4A6E')
        ws.row_dimensions[1].height = 30
        ws.append([])

        headers = ['CODIGO', 'UF', 'DESCRIPCION', 'MODELO', 'UNIDAD', 'CNTD', 'P.U.', 'IMPORTE']
        ws.append(headers)
        for col_idx in range(1, 9):
            cell = ws.cell(row=3, column=col_idx)
            cell.fill = apu_header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[3].height = 28
        col_widths = [12, 30, 40, 20, 12, 10, 16, 18]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        cat_idx = 0
        for cat_name, cat_data in categorias.items():
            cat_idx += 1
            letter = chr(64 + cat_idx) if cat_idx <= 26 else str(cat_idx)
            ws.append([letter, '', cat_name.upper(), '', '', '', cat_data['total']])
            r = ws.max_row
            ws.merge_cells(f'B{r}:F{r}')
            for col in range(1, 9):
                ws.cell(row=r, column=col).fill = cat_fill
                ws.cell(row=r, column=col).font = cat_font
            ws.cell(row=r, column=8).number_format = money_fmt
            ws.cell(row=r, column=8).alignment = Alignment(horizontal='right')

            group_start = ws.max_row + 1
            for j, item in enumerate(cat_data['items'], 1):
                ws.append([f'{letter}.{j}', item['ubicacion'], item['nombre'], item['modelo'], item['unidades'], item['cantidad'], item['precio_unitario'], item['costo']])
                ir = ws.max_row
                for col in range(1, 9):
                    ws.cell(row=ir, column=col).font = item_font
                    ws.cell(row=ir, column=col).border = thin_border
                ws.cell(row=ir, column=5).number_format = '#,##0.00'
                ws.cell(row=ir, column=6).number_format = money_fmt
                ws.cell(row=ir, column=7).number_format = money_fmt

            group_end = ws.max_row
            if group_end >= group_start:
                ws.row_dimensions.group(group_start, group_end, outline_level=1, hidden=False)

        ws.append([])
        ws.append(['', '', '', '', '', '', 'TOTAL GENERAL', sum(c['total'] for c in categorias.values())])
        r = ws.max_row
        for col in range(1, 9):
            ws.cell(row=r, column=col).fill = total_fill
            ws.cell(row=r, column=col).font = total_font
        ws.cell(row=r, column=8).number_format = money_fmt

    else:
        # ── DETALLE DE ACTIVOS ──
        ws.title = f"Detalle REPEX {repex.anio}"
        items_qs = repex.items.select_related(
            'activo', 'activo__modelo', 'activo__modelo__marca',
            'activo__modelo__categoria', 'activo__ubicacion', 'activo__familia'
        ).all()
        
        categorias = OrderedDict()
        for item in items_qs:
            activo = item.activo
            cat_name = '-'
            if activo:
                if activo.modelo and activo.modelo.categoria:
                    cat = activo.modelo.categoria
                    path = [cat.nombre]
                    curr = cat.padre
                    while curr:
                        path.append(curr.nombre)
                        curr = curr.padre
                    cat_name = ' → '.join(reversed(path))
            else:
                cat_name = item.categoria_manual or 'Sin Categoría'
            
            if cat_name not in categorias:
                categorias[cat_name] = {'items': [], 'total': 0.0}
            
            val = {
                'codigo': activo.codigo_interno if activo else '-',
                'nombre': item.display_nombre,
                'marca': (activo.modelo.marca.nombre if activo.modelo and activo.modelo.marca else '-') if activo else '-',
                'modelo': (activo.modelo.nombre if activo and activo.modelo else '-') if activo else '-',
                'ubicacion': (activo.ubicacion.ruta_completa if activo and activo.ubicacion else '-') if activo else (item.ubicacion_manual or '-'),
                'prioridad': item.prioridad,
                'costo': float(item.costo_reposicion or 0),
            }
            categorias[cat_name]['items'].append(val)
            categorias[cat_name]['total'] += val['costo']

        ws.merge_cells('A1:H1')
        ws['A1'].value = f"REPEX {repex.anio} — {repex.nombre}"
        ws['A1'].font = Font(name='Calibri', bold=True, size=14, color='2C4A6E')
        ws.row_dimensions[1].height = 30
        ws.append([])

        headers = ['Código', 'Activo', 'Marca', 'Modelo', 'Ruta Ubicación', 'Categoría', 'Prioridad', 'Costo Reposición']
        ws.append(headers)
        for col_idx in range(1, 9):
            cell = ws.cell(row=3, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[3].height = 28
        col_widths = [14, 30, 16, 18, 35, 30, 12, 18]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        for cat_name, cat_data in categorias.items():
            ws.append([f'📁 {cat_name}', '', '', '', '', '', f'{len(cat_data["items"])} activos', cat_data['total']])
            r = ws.max_row
            ws.merge_cells(f'A{r}:F{r}')
            for col in range(1, 9):
                ws.cell(row=r, column=col).fill = PatternFill(start_color='DCE4EF', end_color='DCE4EF', fill_type='solid')
                ws.cell(row=r, column=col).font = cat_font
            ws.cell(row=r, column=8).number_format = money_fmt

            group_start = ws.max_row + 1
            for item in cat_data['items']:
                ws.append([item['codigo'], item['nombre'], item['marca'], item['modelo'], item['ubicacion'], cat_name, item['prioridad'], item['costo']])
                ir = ws.max_row
                for col in range(1, 9):
                    ws.cell(row=ir, column=col).font = item_font
                    ws.cell(row=ir, column=col).border = thin_border
                ws.cell(row=ir, column=8).number_format = money_fmt
                ws.cell(row=ir, column=1).alignment = Alignment(indent=2)

            group_end = ws.max_row
            if group_end >= group_start:
                ws.row_dimensions.group(group_start, group_end, outline_level=1, hidden=False)

        ws.append([])
        ws.append(['', '', '', '', '', '', 'TOTAL INVERSIÓN', sum(c['total'] for c in categorias.values())])
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
    Cada REPEXItem tiene un único costo_reposicion que se asigna al mes de fecha_proyectada.
    """
    meses_nombres = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                     'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    items = repex.items.select_related('activo', 'activo__familia').all()

    # Agrupar por Familia
    familias = {}
    for item in items:
        if item.activo:
            familia_nombre = item.activo.familia.nombre if item.activo.familia else "Sin Familia"
            familia_id = item.activo.familia.id if item.activo.familia else 0
        else:
            familia_nombre = item.categoria_manual or "Ítems Manuales"
            familia_id = -1  # ID especial para manuales

        key = (familia_id, familia_nombre)

        if key not in familias:
            familias[key] = {
                'familia_nombre': familia_nombre,
                'familia_id': familia_id,
                'items': [],
                'mensual': [0.0] * 12,
                'total': 0.0,
            }

        # Determinar en qué mes cae este item
        item_mensual = [0.0] * 12
        costo = float(item.costo_reposicion or 0)
        mes_proyectado = None

        if item.fecha_proyectada and item.fecha_proyectada.year == repex.anio:
            mes_idx = item.fecha_proyectada.month - 1
            item_mensual[mes_idx] = costo
            mes_proyectado = mes_idx + 1
        elif item.fecha_proyectada is None and costo > 0:
            # Sin fecha, mostrar sin asignar a ningún mes (total suelto)
            pass

        familias[key]['items'].append({
            'id': item.id,
            'activo_nombre': item.display_nombre,
            'descripcion': item.descripcion or '',
            'prioridad': item.prioridad,
            'costo_reposicion': costo,
            'costo_original': float(item.costo_original or 0),
            'mensual': item_mensual,
            'total': costo,
            'mes_proyectado': mes_proyectado,
        })

        # Acumular en familia
        for i in range(12):
            familias[key]['mensual'][i] += item_mensual[i]
        familias[key]['total'] += costo

    # Ordenar familias por nombre
    familias_data = sorted(familias.values(), key=lambda x: x['familia_nombre'])

    # Totales globales
    total_mensual = [0.0] * 12
    total_general = 0.0
    total_items = 0

    for fam in familias_data:
        total_items += len(fam['items'])
        for i in range(12):
            total_mensual[i] += fam['mensual'][i]
        total_general += fam['total']

    return {
        'familias_data': familias_data,
        'meses_nombres': meses_nombres,
        'total_mensual': total_mensual,
        'total_general': total_general,
        'total_items': total_items,
    }


@login_required
def api_update_repex_item(request):
    """Actualiza costo_reposicion y fecha_proyectada de un REPEXItem."""
    if request.method == "POST":
        import json
        from .models import REPEXItem
        from django.http import JsonResponse
        from datetime import date

        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            mes = int(data.get('mes'))
            monto = float(data.get('monto'))

            item = get_object_or_404(REPEXItem, pk=item_id)
            item.costo_reposicion = monto
            if monto > 0 and 1 <= mes <= 12:
                item.fecha_proyectada = date(item.repex.anio, mes, 1)
            elif monto == 0:
                item.fecha_proyectada = None
                item.costo_reposicion = 0

            item.save()
            return JsonResponse({'status': 'ok', 'new_total': float(item.costo_reposicion)})

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
    import json

    try:
        data = json.loads(request.body)
        repex_id = data.get('repex_id')
        nombre = data.get('nombre_item', '').strip()
        ubicacion = data.get('ubicacion_manual', '').strip()
        categoria = data.get('categoria_manual', '').strip()
        unidades_val = data.get('unidades', '').strip()
        cantidad_val = data.get('cantidad', 1)
        precio_val = data.get('precio_unitario', 0)
        prioridad = data.get('prioridad', 'MEDIA')

        if not repex_id or not nombre:
            return JsonResponse({'status': 'error', 'message': 'Nombre del ítem y REPEX son requeridos.'}, status=400)

        repex = REPEX.objects.get(pk=repex_id)

        item = REPEXItem(
            repex=repex,
            activo=None,
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
