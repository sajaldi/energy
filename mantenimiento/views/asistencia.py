from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import TemplateView, View
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from ..models import TecnicoPuesto, Asistencia, Empresa
import datetime

class AsistenciaStationView(LoginRequiredMixin, TemplateView):
    template_name = 'mantenimiento/asistencia_station.html'

class AsistenciaKioskView(LoginRequiredMixin, TemplateView):
    """
    Vista optimizada y exclusiva (App) para el kiosko de asistencia.
    """
    template_name = 'mantenimiento/asistencia_kiosk.html'

class AsistenciaProcessView(LoginRequiredMixin, View):
    """
    Endpoint AJAX para procesar el escaneo de un código QR.
    """
    def post(self, request, *args, **kwargs):
        codigo = request.POST.get('codigo', '').strip()
        if not codigo:
            return JsonResponse({'success': False, 'message': 'Código no proporcionado'}, status=400)
        
        # 1. Buscar al técnico por el código de asistencia
        tecnico = TecnicoPuesto.objects.filter(codigo_asistencia=codigo).first()
        if not tecnico:
            return JsonResponse({
                'success': False, 
                'status': 'LINK_REQUIRED',
                'codigo': codigo,
                'message': f'Código {codigo} no reconocido. ¿Desea vincularlo a un técnico?'
            }, status=404)
        
        # 2. Validar Vigencia
        if not tecnico.esta_vigente:
            return JsonResponse({
                'success': False, 
                'message': 'ACCESO DENEGADO: Técnico con estatus NO VIGENTE.',
                'tecnico': {
                    'nombre': str(tecnico),
                    'foto': tecnico.foto.url if tecnico.foto else None
                }
            }, status=403)
        
        # 3. Procesar Asistencia (Entrada/Salida Inteligente)
        hoy = timezone.now().date()
        ahora = timezone.now().time()
        
        # Buscar el último registro de hoy para este técnico
        ultima_asistencia = Asistencia.objects.filter(tecnico=tecnico, fecha=hoy).order_by('-creado_en').first()
        force_action = request.POST.get('force_action')
        
        tipo_registro = "ENTRADA"

        # Prevención de Doble Escaneo (3 Minutos)
        if ultima_asistencia and not force_action:
            import datetime as dt
            ahora_dt = dt.datetime.combine(hoy, ahora)
            if ultima_asistencia.hora_salida:
                ult_mov_dt = dt.datetime.combine(hoy, ultima_asistencia.hora_salida)
                ult_tipo = "SALIDA"
            else:
                ult_mov_dt = dt.datetime.combine(hoy, ultima_asistencia.hora_entrada)
                ult_tipo = "ENTRADA"
            
            # Si el último movimiento fue hace menos de 3 minutos
            if (ahora_dt - ult_mov_dt).total_seconds() < 180:
                return JsonResponse({
                    'success': False, 
                    'status': 'CONFIRM_ACTION',
                    'message': f'Última acción ({ult_tipo}) fue hace unos instantes. ¿Qué desea registrar ahora?',
                    'tecnico': {
                        'id': tecnico.id,
                        'nombre': str(tecnico),
                        'puesto': tecnico.puesto.nombre if tecnico.puesto else "General",
                        'empresa': tecnico.empresa.nombre if tecnico.empresa else "Independiente",
                        'foto': tecnico.foto.url if tecnico.foto else None
                    }
                }, status=409)

        if force_action == "SALIDA" or (not force_action and ultima_asistencia and not ultima_asistencia.hora_salida):
            # Registrar SALIDA
            if ultima_asistencia and not ultima_asistencia.hora_salida:
                ultima_asistencia.hora_salida = ahora
                ultima_asistencia.save()
            tipo_registro = "SALIDA"
        else:
            # Registrar ENTRADA (ya sea por flujo normal o forzado)
            Asistencia.objects.create(
                tecnico=tecnico, 
                fecha=hoy,
                hora_entrada=ahora,
                usuario_estacion=request.user,
                empresa_registro=tecnico.empresa
            )
            
        return JsonResponse({
            'success': True,
            'message': f'{tipo_registro} REGISTRADA EXITOSAMENTE',
            'tipo': tipo_registro,
            'tecnico': {
                'id': tecnico.id,
                'nombre': str(tecnico),
                'puesto': tecnico.puesto.nombre if tecnico.puesto else "General",
                'empresa': tecnico.empresa.nombre if tecnico.empresa else "Independiente",
                'foto': tecnico.foto.url if tecnico.foto else None
            },
            'hora': ahora.strftime('%I:%M %p')
        })

class AsistenciaReportView(LoginRequiredMixin, TemplateView):
    template_name = 'mantenimiento/reporte_asistencia.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Parámetros de filtro
        fecha_desde_str = self.request.GET.get('fecha_desde')
        fecha_hasta_str = self.request.GET.get('fecha_hasta')
        empresa_id = self.request.GET.get('empresa')
        
        # Defaults: última semana
        hoy = timezone.now().date()
        if fecha_desde_str:
            fecha_desde = datetime.datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
        else:
            fecha_desde = hoy - datetime.timedelta(days=7)
        
        if fecha_hasta_str:
            fecha_hasta = datetime.datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        else:
            fecha_hasta = hoy
        
        # Query base
        asistencias = Asistencia.objects.filter(
            fecha__gte=fecha_desde,
            fecha__lte=fecha_hasta
        ).select_related('tecnico', 'tecnico__puesto', 'tecnico__empresa', 'empresa_registro')
        
        if empresa_id:
            asistencias = asistencias.filter(empresa_registro_id=empresa_id)
        
        # Agrupar por fecha → por empresa
        from collections import OrderedDict
        # Limpiar ordenamiento para que distinct() funcione solo sobre fecha en PostgreSQL
        fechas_set = asistencias.order_by().values_list('fecha', flat=True).distinct().order_by('-fecha')
        
        reporte_por_dia = []
        total_general = 0
        
        for fecha in fechas_set:
            asist_dia = asistencias.filter(fecha=fecha)
            empresas_dia = Empresa.objects.filter(
                pk__in=asist_dia.values_list('empresa_registro', flat=True).distinct()
            ).order_by('nombre')
            
            bloques_empresa = []
            for emp in empresas_dia:
                asist_emp = asist_dia.filter(empresa_registro=emp).order_by('tecnico__nombre', 'tecnico__apellido', 'hora_entrada')
                
                # Agrupar por Técnico para evitar filas repetidas
                tecnicos_map = OrderedDict()
                
                for a in asist_emp:
                    t_id = a.tecnico_id
                    if t_id not in tecnicos_map:
                        tecnicos_map[t_id] = {
                            'tecnico': a.tecnico,
                            'marcaciones': [],
                            'total_segundos': 0,
                            'esta_adentro': False
                        }
                    
                    tecnicos_map[t_id]['marcaciones'].append(a)
                    
                    # Calcular duración si tiene entrada y salida
                    if a.hora_entrada and a.hora_salida:
                        # Usamos la misma fecha base para la resta de tiempos
                        dt_entrada = datetime.datetime.combine(a.fecha, a.hora_entrada)
                        dt_salida = datetime.datetime.combine(a.fecha, a.hora_salida)
                        delta = dt_salida - dt_entrada
                        tecnicos_map[t_id]['total_segundos'] += delta.total_seconds()
                    
                    # Si alguna marcación no tiene salida, sigue "adentro"
                    if not a.hora_salida:
                        tecnicos_map[t_id]['esta_adentro'] = True
                
                # Post-procesar para formato de duración
                for t_id, data in tecnicos_map.items():
                    ts = data['total_segundos']
                    horas = int(ts // 3600)
                    minutos = int((ts % 3600) // 60)
                    data['duracion_total'] = f"{horas}h {minutos}m" if ts > 0 else "---"

                bloques_empresa.append({
                    'empresa': emp,
                    'total': len(tecnicos_map),
                    'tecnicos_data': tecnicos_map.values()
                })
            
            total_dia = asist_dia.count()
            total_general += total_dia
            reporte_por_dia.append({
                'fecha': fecha,
                'total_dia': total_dia,
                'empresas': bloques_empresa
            })
        
        context['fecha_desde'] = fecha_desde
        context['fecha_hasta'] = fecha_hasta
        context['empresa_filtro'] = empresa_id
        context['empresas_catalogo'] = Empresa.objects.all().order_by('nombre')
        context['reporte_por_dia'] = reporte_por_dia
        context['total_general'] = total_general
        return context

class BuscarTecnicosSinVincularView(LoginRequiredMixin, View):
    """
    Retorna técnicos vigentes que aún no tienen un código de asistencia vinculado.
    """
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        tecnicos = TecnicoPuesto.objects.filter(
            esta_vigente=True
        ).filter(
            Q(codigo_asistencia__isnull=True) | Q(codigo_asistencia='')
        )
        
        if query:
            tecnicos = tecnicos.filter(
                Q(nombre__icontains=query) | 
                Q(apellido__icontains=query) |
                Q(dni__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__username__icontains=query)
            )
            
        results = []
        for t in tecnicos[:20]:
            results.append({
                'id': t.id,
                'nombre': str(t),
                'puesto': t.puesto.nombre if t.puesto else "General",
                'empresa': t.empresa.nombre if t.empresa else "Independiente",
                'foto': t.foto.url if t.foto else None
            })
            
        return JsonResponse({'success': True, 'results': results})

class VincularTecnicoCodigoView(LoginRequiredMixin, View):
    """
    Vincula un código a un técnico y registra su asistencia inmediatamente.
    """
    def post(self, request, *args, **kwargs):
        tecnico_id = request.POST.get('tecnico_id')
        codigo = request.POST.get('codigo', '').strip()
        
        if not tecnico_id or not codigo:
            return JsonResponse({'success': False, 'message': 'Datos incompletos.'}, status=400)
            
        tecnico = get_object_or_404(TecnicoPuesto, id=tecnico_id)
        
        # Validar que el código no lo tenga ya alguien más (doble check)
        if TecnicoPuesto.objects.filter(codigo_asistencia=codigo).exists():
            return JsonResponse({'success': False, 'message': 'Este código ya fue vinculado a otro técnico hace unos instantes.'}, status=400)
            
        # 1. Vincular
        tecnico.codigo_asistencia = codigo
        tecnico.save()
        
        # 2. Registrar Asistencia (Entrada Directa tras vínculo)
        hoy = timezone.now().date()
        ahora = timezone.now().time()
        
        # Al vincular, siempre es una nueva entrada
        Asistencia.objects.create(
            tecnico=tecnico, 
            fecha=hoy,
            hora_entrada=ahora,
            usuario_estacion=request.user,
            empresa_registro=tecnico.empresa
        )
        
        return JsonResponse({
            'success': True,
            'message': f'VÍNCULO EXITOSO. Entrada registrada para {tecnico}',
            'tecnico': {
                'nombre': str(tecnico),
                'puesto': tecnico.puesto.nombre if tecnico.puesto else "General",
                'empresa': tecnico.empresa.nombre if tecnico.empresa else "Independiente",
                'foto': tecnico.foto.url if tecnico.foto else None
            },
            'hora': ahora.strftime('%I:%M %p')
        })

class AsistenciaEnVivoView(LoginRequiredMixin, View):
    """
    Retorna el listado de personal actualmente "ADENTRO" (entrada sin salida hoy),
    agrupado por empresa.
    """
    def get(self, request, *args, **kwargs):
        hoy = timezone.now().date()
        
        # Obtener los IDs de técnicos que tienen una entrada hoy pero NO han marcado salida en ese mismo registro
        # Ojo: Buscamos el ÚLTIMO registro de hoy para cada técnico
        registros_activos = Asistencia.objects.filter(
            fecha=hoy,
            hora_salida__isnull=True
        ).select_related('tecnico', 'tecnico__puesto', 'empresa_registro')

        reporte = {}
        for reg in registros_activos:
            empresa_obj = reg.empresa_registro or reg.tecnico.empresa
            emp_nombre = empresa_obj.nombre if empresa_obj else "Independiente"
            
            if emp_nombre not in reporte:
                reporte[emp_nombre] = {
                    'conteo': 0,
                    'logo': empresa_obj.logo.url if empresa_obj and hasattr(empresa_obj, 'logo') and empresa_obj.logo else None,
                    'personal': []
                }
            
            reporte[emp_nombre]['personal'].append({
                'nombre': str(reg.tecnico),
                'puesto': reg.tecnico.puesto.nombre if reg.tecnico.puesto else "Técnico",
                'foto': reg.tecnico.foto.url if reg.tecnico.foto else None,
                'hora_entrada': reg.hora_entrada.strftime('%I:%M %p')
            })
            reporte[emp_nombre]['conteo'] += 1

        return JsonResponse({
            'success': True,
            'fecha': hoy.strftime('%d/%m/%Y'),
            'reporte': reporte,
            'total_adentro': registros_activos.count()
        })

class BuscarPersonalGestorView(LoginRequiredMixin, View):
    """
    Retorna la lista de personal para ser editada y catálogos de empresa y puesto.
    """
    def get(self, request, *args, **kwargs):
        try:
            from ..models import PuestoTrabajo
            query = request.GET.get('q', '').strip()
            
            # Ordenamos para darle prioridad a los más recientes o al menos ordenarlos consistentemente
            tecnicos = TecnicoPuesto.objects.filter(esta_vigente=True).order_by('-id')
            
            if query:
                tecnicos = tecnicos.filter(
                    Q(nombre__icontains=query) | 
                    Q(apellido__icontains=query) |
                    Q(user__first_name__icontains=query) |
                    Q(user__last_name__icontains=query) |
                    Q(dni__icontains=query) |
                    Q(codigo_asistencia__icontains=query)
                )
                
            results = []
            for t in tecnicos[:50]: # Subimos a 50 para que vean más opciones por defecto
                nombre_real = t.nombre or (t.user.first_name if getattr(t, 'user', None) else '')
                apellido_real = t.apellido or (t.user.last_name if getattr(t, 'user', None) else '')
                # Fallback si todo está vacío
                if not nombre_real and not apellido_real:
                    nombre_real = t.user.username if getattr(t, 'user', None) else "Sin Nombre"
                    
                results.append({
                    'id': t.id,
                    'nombre': nombre_real,
                    'apellido': apellido_real,
                    'dni': t.dni or '',
                    'codigo_asistencia': t.codigo_asistencia or '',
                    'puesto_id': t.puesto_id,
                    'empresa_id': t.empresa_id,
                    'fecha_nacimiento': t.fecha_nacimiento.strftime('%Y-%m-%d') if t.fecha_nacimiento else '',
                    'fecha_alta': t.fecha_alta.strftime('%Y-%m-%d') if t.fecha_alta else '',
                    'tipo_sangre': t.tipo_sangre or '',
                    'esta_vigente': t.esta_vigente,
                    'horas_semanales_max': str(t.horas_semanales_max),
                    'historial': [
                        {
                            'fecha': a.fecha.strftime('%d/%m/%Y'),
                            'entrada': a.hora_entrada.strftime('%I:%M %p') if a.hora_entrada else '--:--',
                            'salida': a.hora_salida.strftime('%I:%M %p') if a.hora_salida else '--:--'
                        }
                        for a in t.asistencias.all().order_by('-fecha', '-hora_entrada')[:5]
                    ] if hasattr(t, 'asistencias') else [],
                    'foto': t.foto.url if (t.foto and getattr(t.foto, 'name', None)) else None
                })
                
            # Catálogos para los selects del form
            empresas = list(Empresa.objects.values('id', 'nombre'))
            puestos = list(PuestoTrabajo.objects.values('id', 'nombre'))
            
            return JsonResponse({
                'success': True, 
                'results': results,
                'empresas': empresas,
                'puestos': puestos
            })
        except Exception as e:
            import traceback
            print("ERROR EN BUSQUEDA:", traceback.format_exc())
            return JsonResponse({'success': False, 'message': str(e), 'results': []}, status=200)

class GestionarPersonalView(LoginRequiredMixin, View):
    """
    Recibe la actualización de datos y base64 de la foto para un técnico.
    """
    def post(self, request, *args, **kwargs):
        import base64
        from django.core.files.base import ContentFile
        import uuid

        tecnico_id = request.POST.get('id')
        if not tecnico_id:
            # Opción de crear nuevo si quieres expandirlo luego
            return JsonResponse({'success': False, 'message': 'ID de técnico requerido para editar.'}, status=400)
            
        tecnico = get_object_or_404(TecnicoPuesto, id=tecnico_id)
        
        # Validar DNI único
        dni = request.POST.get('dni', '').strip()
        if dni and TecnicoPuesto.objects.filter(dni=dni).exclude(id=tecnico.id).exists():
            return JsonResponse({'success': False, 'message': 'Ese DNI ya está registrado en otro perfil.'}, status=400)

        # Validar Código Asistencia único
        codigo = request.POST.get('codigo_asistencia', '').strip()
        if codigo and TecnicoPuesto.objects.filter(codigo_asistencia=codigo).exclude(id=tecnico.id).exists():
            return JsonResponse({'success': False, 'message': 'Ese Código QR ya está vinculado a otro técnico.'}, status=400)

        tecnico.nombre = request.POST.get('nombre', '').strip() or tecnico.nombre
        tecnico.apellido = request.POST.get('apellido', '').strip() or tecnico.apellido
        tecnico.dni = dni or None
        tecnico.codigo_asistencia = codigo or None
        
        emp_id = request.POST.get('empresa_id')
        if emp_id:
            tecnico.empresa_id = emp_id
            
        pue_id = request.POST.get('puesto_id')
        if pue_id:
            tecnico.puesto_id = pue_id

        # Nuevos campos
        fn = request.POST.get('fecha_nacimiento')
        if fn: tecnico.fecha_nacimiento = fn
        else: tecnico.fecha_nacimiento = None
            
        fa = request.POST.get('fecha_alta')
        if fa: tecnico.fecha_alta = fa
        else: tecnico.fecha_alta = None
            
        tecnico.tipo_sangre = request.POST.get('tipo_sangre', '')
        
        # Checkbox booleano
        vigente = request.POST.get('esta_vigente')
        tecnico.esta_vigente = (vigente == 'true' or vigente == '1')
        
        # Float
        horas = request.POST.get('horas_semanales_max')
        if horas:
            try:
                tecnico.horas_semanales_max = float(horas)
            except ValueError:
                pass

        # Procesar foto (Base64)
        foto_b64 = request.POST.get('foto_base64')
        if foto_b64 and foto_b64.startswith('data:image'):
            try:
                format, imgstr = foto_b64.split(';base64,') 
                ext = format.split('/')[-1]
                filename = f"foto_{uuid.uuid4().hex[:8]}.{ext}"
                data = ContentFile(base64.b64decode(imgstr), name=filename)
                
                if tecnico.foto:
                    tecnico.foto.delete(save=False) # Borra la anterior
                tecnico.foto = data
            except Exception as e:
                pass # Fallback si el string está mal formado
                
        tecnico.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Perfil actualizado correctamente.',
            'foto': tecnico.foto.url if tecnico.foto else None
        })
