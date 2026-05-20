import json
import os

class GameData:
    def __init__(self, data_dir='api_responses'):
        self.data_dir = os.path.join(os.path.dirname(__file__), data_dir)
        self.activities = []
        self.activities_map = {}
        self.items_map = {}
        self.skills_map = {}
        self.global_variables = []
        
        self.load_data()

    def _load_json(self, filename):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        print(f"[Aviso] Arquivo não encontrado: {path}")
        return None

    def load_data(self):
        """Carrega e indexa todos os dados cruciais do jogo."""
        # Carregar Atividades
        activities_data = self._load_json('activities.json')
        if activities_data:
            self.activities = activities_data
            # Mapeamento para busca rápida por ID
            self.activities_map = {act['id']: act for act in activities_data}

        # Carregar e planificar Itens (Categorizados)
        categorized_items = self._load_json('items_categorized.json')
        if categorized_items:
            for category_group in categorized_items:
                for category in category_group.get('categories', []):
                    for item in category.get('items', []):
                        # Guarda o item completo pelo seu ID base
                        self.items_map[item['id']] = item
        
        # Carregar Skills
        skills_data = self._load_json('skills.json')
        if skills_data:
            self.skills_map = {skill['id']: skill for skill in skills_data}
            
        # Carregar Variáveis Globais (usado para bônus de fine inputs, etc)
        global_vars = self._load_json('global_variables.json')
        if global_vars:
            self.global_variables = global_vars

if __name__ == "__main__":
    # Teste rápido do carregamento
    db = GameData()
    print(f"Banco de dados carregado: {len(db.items_map)} Itens e {len(db.activities_map)} Atividades.")