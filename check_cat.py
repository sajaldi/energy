from activos.models import Categoria

cats = Categoria.objects.filter(nombre__icontains='TRANSFERENCIA')
print(f"Encontradas: {cats.count()}")
for c in cats:
    print(f"Id: {c.id}, Nombre: {c.nombre}, Padre: {c.padre.nombre if c.padre else 'NINGUNO'}, Nivel: {c.nivel}")
