import json
import os
import sys
import requests

# Añadir el directorio raíz al path para poder importar client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client import InfolegClient

def update_configs():
    print("Iniciando actualización de configuraciones desde InfoLeg...")
    try:
        client = InfolegClient()
        session = requests.Session()
        
        # Usamos la interfaz oficial del cliente que ya devuelve modelos Pydantic
        configs = client.mostrar_opciones_busqueda_de_normas(session)
        
        # Convertimos los modelos a diccionarios para serialización JSON
        deps = [d.model_dump() for d in configs.dependencias]
        tipos = [t.model_dump() for t in configs.tipos_norma]
        
        os.makedirs("data", exist_ok=True)
        
        with open("data/dependencias.json", "w", encoding="utf-8") as f:
            json.dump(deps, f, indent=2, ensure_ascii=False)
        print(f"Se guardaron {len(deps)} dependencias en data/dependencias.json")
            
        with open("data/tipos_norma.json", "w", encoding="utf-8") as f:
            json.dump(tipos, f, indent=2, ensure_ascii=False)
        print(f"Se guardaron {len(tipos)} tipos de norma en data/tipos_norma.json")
        
    except Exception as e:
        print(f"Error durante la actualización: {e}")

if __name__ == "__main__":
    update_configs()
