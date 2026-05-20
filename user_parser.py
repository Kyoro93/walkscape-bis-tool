import base64
import gzip
import json

class UserData:
    def __init__(self, save_string=None):
        self.raw_data = {}
        self.skill_levels = {}
        self.owned_base_items = set()
        self.steps = 0
        self.character_level = 1
        
        if save_string:
            self.load_from_string(save_string)

    def load_from_string(self, s):
        """Tenta decodificar a string copiada do jogo."""
        s = s.strip()
        try:
            # A maioria dos exports de Walkscape usa Base64 + Gzip
            decoded_bytes = base64.b64decode(s)
            decompressed_bytes = gzip.decompress(decoded_bytes)
            self.raw_data = json.loads(decompressed_bytes.decode('utf-8'))
        except Exception:
            try:
                # Fallback caso já seja um JSON limpo
                self.raw_data = json.loads(s)
            except Exception as e:
                print(f"Erro ao processar save do usuário: {e}")
                return False
        
        self._parse_stats()
        self._parse_inventory()
        return True

    def _parse_stats(self):
        """Extrai as estatísticas e converte os steps em nível do personagem."""
        self.skill_levels = self.raw_data.get('skills', {})
        self.steps = self.raw_data.get('steps', 0)
        # Aproximação muito rústica para nível de personagem baseada nos steps 
        # O Walkscape converte os passos em Level usando constantes, mas por enquanto:
        self.character_level = max(1, min(99, int((self.steps / 1000) ** 0.5))) 

    def _parse_inventory(self):
        """
        Agrupa todas as áreas do inventário e limpa os sufixos de qualidade.
        Isso nos diz se o jogador "possui" pelo menos um item daquele tipo,
        independente de ser Common ou Legendary.
        """
        self.owned_base_items = set()
        
        # Categoria de locais onde os itens podem estar no save
        categories = [
            'inventory', 'bank', 'gear', 'collectibles', 
            'consumables', 'pets', 'available_pets', 'available_eggs'
        ]
        
        for cat in categories:
            items = self.raw_data.get(cat, {})
            if isinstance(items, dict):
                for item_key in items.keys():
                    base_id = self._strip_quality_suffix(item_key)
                    self.owned_base_items.add(base_id)
            elif isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and 'id' in item:
                        self.owned_base_items.add(self._strip_quality_suffix(item['id']))
                    elif isinstance(item, str):
                        self.owned_base_items.add(self._strip_quality_suffix(item))

    def _strip_quality_suffix(self, item_key):
        """Limpa sufixos (ex: iron_pickaxe_rare -> iron_pickaxe)."""
        suffixes = [
            '_fine', '_consumableFine', '_consumableCommon',
            '_common', '_uncommon', '_rare', '_epic', '_legendary', '_ethereal'
        ]
        for s in suffixes:
            if item_key.endswith(s):
                return item_key[:-len(s)]
        return item_key