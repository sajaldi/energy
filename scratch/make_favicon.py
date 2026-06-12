from PIL import Image

input_path = r"C:\Users\Saul\.gemini\antigravity-ide\brain\4fd52898-d0d4-4a04-94bd-c21cf1fd730d\favicon_buildings_1781264691179.png"
output_path1 = r"d:\Apps\energia\energy\static\favicon.ico"
output_path2 = r"d:\Apps\energia\energy\favicon.ico"

try:
    img = Image.open(input_path)
    # Resize and save as .ico
    img.save(output_path1, format='ICO', sizes=[(16, 16), (32, 32), (64, 64)])
    img.save(output_path2, format='ICO', sizes=[(16, 16), (32, 32), (64, 64)])
    print("Favicon saved successfully!")
except Exception as e:
    print("Error:", e)
