import collections
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from ..models import TecnicoPuesto, PuestoTrabajo, OrdenTrabajo

@staff_member_required
def dashboard_cargas(request):
    now = timezone.now(); monday = now - timedelta(days=now.weekday()); semanas = []
    for i in range(4):
        start = monday + timedelta(weeks=i); end = start + timedelta(days=6); anio, sem, _ = start.isocalendar()
        semanas.append({'label': f"Semana {sem}", 'rango': f"{start.strftime('%d/%m')} - {end.strftime('%d/%m')}", 'key': f"{anio}-{sem}", 'start': start, 'end': end})
    tecnicos = TecnicoPuesto.objects.select_related('user', 'puesto').filter(disponible=True); puestos = PuestoTrabajo.objects.all()
    q_start = timezone.make_aware(datetime.combine(semanas[0]['start'], datetime.min.time())); q_end = timezone.make_aware(datetime.combine(semanas[-1]['end'], datetime.max.time()))
    ots = OrdenTrabajo.objects.filter(tecnico__isnull=False, inicio_programado__gte=q_start, inicio_programado__lte=q_end).select_related('rutina', 'aviso', 'ubicacion'); cm = collections.defaultdict(lambda: {'horas': 0.0, 'ots': []})
    for ot in ots:
        anio, sem, _ = ot.inicio_programado.isocalendar(); key = f"{anio}-{sem}"; dur = (ot.fin_programado - ot.inicio_programado).total_seconds() / 3600
        cm[(ot.tecnico_id, key)]['horas'] += float(dur); cm[(ot.tecnico_id, key)]['ots'].append({'id': ot.id, 'nombre': ot.rutina.nombre if ot.rutina else (ot.aviso.descripcion[:30] if ot.aviso else "OT"), 'ubicacion': ot.ubicacion.nombre if ot.ubicacion else "S/U", 'inicio': ot.inicio_programado.strftime('%d/%m %H:%M'), 'horas': round(dur, 1), 'estado': ot.estado})
    td = []
    for t in tecnicos:
        st = []
        for s in semanas:
            d = cm.get((t.user_id, s['key']), {'horas': 0.0, 'ots': []}); hrs = d['horas']; cap = float(t.horas_semanales_max); pct = (hrs/cap*100) if cap > 0 else 0
            st.append({'horas': round(hrs, 1), 'pct': round(min(pct, 100), 1), 'total_pct': round(pct, 1), 'capacidad': cap, 'is_over': pct > 100, 'ots': d['ots']})
        td.append({'id': t.user_id, 'nombre': t.user.get_full_name() or t.user.username, 'puesto': t.puesto.nombre, 'semanas': st})
    pd = []
    for p in puestos:
        pt = [t for t in tecnicos if t.puesto_id == p.id]
        if not pt: continue
        ct = sum(float(t.horas_semanales_max) for t in pt); sp = []
        for s in semanas:
            hp = sum(cm.get((t.user_id, s['key']), {'horas': 0.0})['horas'] for t in pt); pct = (hp/ct*100) if ct > 0 else 0
            sp.append({'horas': round(hp, 1), 'pct': round(min(pct, 100), 1), 'total_pct': round(pct, 1), 'capacidad': ct, 'is_over': pct > 100})
        pd.append({'nombre': p.nombre, 'semanas': sp})
    return render(request, 'mantenimiento/dashboard_cargas.html', {'semanas': semanas, 'tecnicos': td, 'puestos': pd})
