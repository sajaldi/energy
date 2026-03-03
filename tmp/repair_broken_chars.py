
from mantenimiento.models import Categoria, Rutina, OrdenTrabajo
from activos.models import Ubicacion, Activo
import re

# Mapeo de fragmentos comunes con ?? a sus versiones correctas
# El orden importa: los más largos o específicos primero
REPLACEMENTS = [
    (r"S??tano", "Sótano"),
    (r"S??tano", "Sótano"),
    (r"ba??o", "baño"),
    (r"BA??O", "BAÑO"),
    (r"pa??ales", "pañales"),
    (r"??REA", "ÁREA"),
    (r"COM??N", "COMÚN"),
    (r"presi??n", "presión"),
    (r"PRESI??N", "PRESIÓN"),
    (r"V??lvula", "Válvula"),
    (r"V??LVULA", "VÁLVULA"),
    (r"V??vula", "Válvula"), # Error de dedo en el original
    (r"centr??fugo", "centrífugo"),
    (r"CENTR??FUGO", "CENTRÍFUGO"),
    (r"centr??fuga", "centrífuga"),
    (r"CENTR??FUGA", "CENTRÍFUGA"),
    (r"Estaci??n", "Estación"),
    (r"ESTACI??N", "ESTACIÓN"),
    (r"inspecci??n", "inspección"),
    (r"INSPECCI??N", "INSPECCIÓN"),
    (r"t??rmico", "térmico"),
    (r"T??RMICO", "TÉRMICO"),
    (r"jab??n", "jabón"),
    (r"JAB??N", "JABÓN"),
    (r"conexi??n", "conexión"),
    (r"CONEXI??N", "CONEXIÓN"),
    (r"bateria", "batería"),
    (r"BATER??A", "BATERÍA"),
    (r"rel??", "relé"),
    (r"REL??", "RELÉ"),
    (r"Recepci??n", "Recepción"),
    (r"RECEPCI??N", "RECEPCIÓN"),
    (r"telef??nica", "telefónica"),
    (r"Met??lica", "Metálica"),
    (r"MET??LICA", "METÁLICA"),
    (r"R??tulo", "Rótulo"),
    (r"R??TULO", "RÓTULO"),
    (r"Rotulo", "Rótulo"),
    (r"Evacuaci??n", "Evacuación"),
    (r"EVACUACI??N", "EVACUACIÓN"),
    (r"N??meros", "Números"),
    (r"p??nico", "pánico"),
    (r"P??NICO", "PÁNICO"),
    (r"t??cnico", "técnico"),
    (r"T??CNICO", "TÉCNICO"),
    (r"T??cnico", "Técnico"),
    (r"Megafon??a", "Megafonía"),
    (r"Inyecci??n", "Inyección"),
    (r"INYECCI??N", "INYECCIÓN"),
    (r"Extracci??n", "Extracción"),
    (r"EXTRACCI??N", "EXTRACCIÓN"),
    (r"Verificaci??n", "Verificación"),
    (r"VERIFICACI??N", "VERIFICACIÓN"),
    (r"alimentaci??n", "alimentación"),
    (r"ALIMENTACI??N", "ALIMENTACIÓN"),
    (r"autom??tico", "automático"),
    (r"AUTOM??TICO", "AUTOMÁTICO"),
    (r"p??blico", "público"),
    (r"P??BLICO", "PÚBLICO"),
    (r"caf??", "café"),
    (r"operaci??n", "operación"),
    (r"OPERACI??N", "OPERACIÓN"),
    (r"cr??tica", "crítica"),
    (r"CR??TICA", "CRÍTICA"),
    (r"C??mara", "Cámara"),
    (r"C??MARA", "CÁMARA"),
    (r"magn??tico", "magnético"),
    (r"MAGN??TICO", "MAGNÉTICO"),
    (r"aspiraci??n", "aspiración"),
    (r"ASPIRACI??N", "ASPIRACIÓN"),
    (r"f??sico", "físico"),
    (r"F??SICO", "FÍSICO"),
    (r"desempe??o", "desempeño"),
    (r"DESEMPE??O", "DESEMPEÑO"),
    (r"peri??dica", "periódica"),
    (r"PERI??DICA", "PERIÓDICA"),
    (r"??ptico", "óptico"),
    (r"??PTICO", "ÓPTICO"),
    (r"protecci??n", "protección"),
    (r"PROTECCI??N", "PROTECCIÓN"),
    (r"dosificaci??n", "dosificación"),
    (r"DOSIFICACI??N", "DOSIFICACIÓN"),
    (r"filtraci??n", "filtración"),
    (r"FILTRACI??N", "FILTRACIÓN"),
    (r"el??ctrico", "eléctrico"),
    (r"EL??CTRICO", "ELÉCTRICO"),
    (r"mec??nico", "mecánico"),
    (r"MEC??NICO", "MECÁNICO"),
    (r"hidrosanitario", "hidrosanitario"),
    (r"HN SPCI", "HN SPCI"),
    (r"??", "ñ"), # Caso genérico si queda algo (riesgo alto)
]

def fix_string(text):
    if not text: return text
    new_text = text
    # Primero reemplazamos el caracter de reemplazo de unicode por ?? para unificar
    new_text = new_text.replace("\ufffd", "??")
    
    for pattern, replacement in REPLACEMENTS:
        # Usamos re.sub con ignore case si fuera necesario, pero aquí el mapeo ya tiene ambas versiones
        new_text = re.sub(re.escape(pattern), replacement, new_text)
    
    return new_text

def repair_model(model, fields):
    print(f"Reparando {model.__name__}...")
    updated_count = 0
    for field in fields:
        q_results = model.objects.filter(**{f"{field}__icontains": "??"}) | model.objects.filter(**{f"{field}__icontains": "\ufffd"})
        for obj in q_results:
            old_val = getattr(obj, field)
            new_val = fix_string(old_val)
            if old_val != new_val:
                setattr(obj, field, new_val)
                obj.save()
                updated_count += 1
    print(f" - {updated_count} campos actualizados.")

if __name__ == "__main__":
    repair_model(Ubicacion, ['nombre'])
    repair_model(Activo, ['nombre', 'descripcion'])
    repair_model(Rutina, ['nombre', 'descripcion'])
    repair_model(OrdenTrabajo, ['notas', 'descripcion_corta'])
    repair_model(Categoria, ['nombre'])
    print("\nProceso de reparación completado.")
