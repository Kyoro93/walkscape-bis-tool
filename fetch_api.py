import os
import requests
import json

# URL Base (Ajuste se estiver rodando uma API local como http://localhost:3001/api)
BASE_URL = 'https://gear.walkscape.app/api'
# __file__ se refere ao arquivo atual. os.path.dirname pega o diretório dele.
# os.path.join junta os caminhos de forma segura para o SO.
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'api_responses')

ENDPOINTS = {
    'abilities.json': 'abilities',
    'skills.json': 'skills',
    'factions.json': 'factions',
    'global_variables.json': 'global_variables',
    'keywords.json': 'keywords',
    'items_categorized.json': 'items/categorized_items',
    'items_materials.json': 'items/search?type=material&detailed=true',
    'items_containers.json': 'items/search?type=container&detailed=true',
    'items_fine_materials.json': 'items/fine_materials',
    'items_url_mapping.json': 'items/url_mapping',
    'items_item_values.json': 'items/item_value_mapping',
    'locations.json': 'locations',
    'locations_realm_defaults.json': 'locations/realm_default_locations',
    'activities.json': 'activities',
    'recipes.json': 'recipes',
    'stats.json': 'stats',
    'lootTables.json': 'lootTables',
    'routes.json': 'routes',
    'terrain_modifiers.json': 'terrain_modifiers',
    'achievements_ap.json': 'achievements/ap'
}

def fetch_all():
    """
    Cria o diretório de saída e busca todos os endpoints,
    salvando as respostas como arquivos JSON formatados.
    """
    # Cria o diretório de saída se ele não existir.
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"Baixando dados da API para o diretório: {OUTPUT_DIR}\n")

    # Itera sobre o dicionário de endpoints.
    for filename, endpoint in ENDPOINTS.items():
        url = f"{BASE_URL}/{endpoint}"
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        try:
            response = requests.get(url, headers={'Accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            print(f"[OK] Salvo: {filename}")

        except requests.exceptions.RequestException as err:
            print(f"[ERRO] Falha ao buscar /{endpoint}: {err}")
        except json.JSONDecodeError:
            print(f"[ERRO] Falha ao decodificar JSON de /{endpoint}")

    print('\nProcesso concluído!')

if __name__ == "__main__":
    fetch_all()
