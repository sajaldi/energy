from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from .models import PresupuestoAnual, PartidaPresupuestaria, GastoEjecutado, ItemPresupuesto, PresupuestoAgrupado
from django.contrib.auth.decorators import login_required
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
