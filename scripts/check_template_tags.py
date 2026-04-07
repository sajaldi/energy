import os
from docxtpl import DocxTemplate

template_path = 'd:\\Apps\\energia\\energy\\tiempo_acordado_template.docx'
if os.path.exists(template_path):
    doc = DocxTemplate(template_path)
    tags = doc.get_undeclared_template_variables()
    print("Tags encontrados en la plantilla de Word:")
    for tag in sorted(tags):
        print(f" - {tag}")
else:
    print("No se encontró la plantilla.")
