from django.conf import settings
from .models import Material

class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('inventory_cart')
        if not cart:
            cart = self.session['inventory_cart'] = {}
        self.cart = cart

    def add(self, material_id, quantity=1, override_quantity=False):
        material_id = str(material_id)
        if material_id not in self.cart:
            self.cart[material_id] = 0
        
        if override_quantity:
            self.cart[material_id] = float(quantity)
        else:
            self.cart[material_id] += float(quantity)
        
        self.save()

    def remove(self, material_id):
        material_id = str(material_id)
        if material_id in self.cart:
            del self.cart[material_id]
            self.save()

    def clear(self):
        self.session['inventory_cart'] = {}
        self.save()

    def save(self):
        self.session.modified = True

    def get_items(self):
        material_ids = self.cart.keys()
        materials = Material.objects.filter(id__in=material_ids)
        items = []
        for m in materials:
            items.append({
                'material': m,
                'quantity': self.cart[str(m.id)],
                'id': m.id
            })
        return items

    def __len__(self):
        return len(self.cart)
