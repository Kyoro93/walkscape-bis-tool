import math
import itertools
from collections import defaultdict

class WalkscapeOptimizer:
    def __init__(self, game_data, user_data=None):
        """
        :param game_data: Instância de GameData (Módulo A)
        :param user_data: Instância de UserData (Módulo B)
        """
        self.game_data = game_data
        self.user_data = user_data

    def optimize(self, activity_id, objective="xp_per_step", use_only_owned=True):
        """
        Encontra o melhor equipamento para a atividade selecionada.
        :param activity_id: ID da atividade (ex: 'unicorn_hunting')
        :param objective: Métrica alvo (ex: 'xp_per_step', 'average_steps_per_action')
        :param use_only_owned: Se True, usa apenas itens que o jogador possui.
        """
        activity = self.game_data.activities_map.get(activity_id)
        if not activity:
            if hasattr(self.game_data, 'recipes_map'):
                activity = self.game_data.recipes_map.get(activity_id)
            elif hasattr(self.game_data, 'recipes'):
                activity = next((r for r in self.game_data.recipes if r['id'] == activity_id), None)
                
        if not activity:
            raise ValueError(f"Tarefa/Receita '{activity_id}' não encontrada no banco de dados.")

        # 1. Identificar Skill relacionada e Nível do Jogador
        related_skills = activity.get('relatedSkillsList') or activity.get('relatedSkills', [])
        related_skill = related_skills[0] if related_skills else None
        player_level = 1
        if self.user_data and related_skill:
            player_level = self.user_data.skill_levels.get(related_skill, 1)
        
        # 2. Identificar Palavras-chave Exigidas pela Atividade (Ex: "hunting_bow")
        required_keywords = set()
        for req in (activity.get('requirements') or []):
            if req.get('type') == 'keywordEquipped':
                required_keywords.add(req['requirement']['keyword'])
            elif req.get('type') == 'distinctKeywordItemsEquipped':
                for kw in req['requirement'].get('keywords', []):
                    required_keywords.add(kw)

        # 3. Filtrar e extrair os status dos itens
        pools = defaultdict(list)
        
        for item in self.game_data.items_map.values():
            # Pular se for restrito ao inventário e o jogador não possuir
            if use_only_owned and self.user_data:
                if item['id'] not in self.user_data.owned_base_items:
                    continue
            
            gear_type = item.get('gearType')
            if not gear_type:
                if item.get('type') == 'consumable':
                    gear_type = 'consumable'
                else:
                    continue # Não é um item equipável
                
            stats = self._extract_item_stats(item, related_skill)
            
            # Pular itens inúteis (status 0 e sem keyword necessária)
            item_keywords = set(item.get('keywords', []))
            has_req_keyword = bool(item_keywords.intersection(required_keywords))
            
            if sum(stats.values()) == 0 and not has_req_keyword:
                continue
                
            # Calcula um "Score Heurístico" bruto para pré-ranqueamento
            # Prioriza WE, DA, redução de passos e XP.
            heuristic_score = (
                stats['we'] * 10 + 
                stats['da'] * 100 + 
                (-stats['steps_flat']) * 100 + 
                stats['xp_pct'] * 100 +
                stats['dr'] * 100 +
                stats['nmc'] * 100
            )
            
            # Bônus massivo no score se o item fornece a ferramenta exigida
            if has_req_keyword:
                heuristic_score += 1000 

            pools[gear_type].append({
                'id': item['id'],
                'name': item['name'],
                'stats': stats,
                'keywords': item_keywords,
                'score': heuristic_score
            })

        # 4. Pré-ranquear e podar (Beam) os pools para não explodir a memória
        # Mantemos apenas os Top 4 itens de cada slot (Top 6 para anéis)
        top_pools = {}
        for slot, items in pools.items():
            sorted_items = sorted(items, key=lambda x: x['score'], reverse=True)
            top_pools[slot] = sorted_items[:6] if slot == 'ring' else sorted_items[:4]

        # Adiciona um item vazio (None) para slots que podem ficar vazios
        for slot in ['head', 'cape', 'back', 'chest', 'hands', 'legs', 'feet', 'neck', 'primary', 'secondary', 'pet', 'tool', 'consumable']:
            if slot not in top_pools:
                top_pools[slot] = []
            top_pools[slot].append(None)

        # 5. Gerar Combinações (A Mágica)
        best_build = None
        best_metric_value = -1 if objective == 'xp_per_step' else float('inf')
        
        # Lidar com os 2 slots de anéis
        ring_combos = list(itertools.combinations_with_replacement(top_pools.get('ring', [None]), 2))
        
        # Lista de slots simples para cruzar
        simple_slots = [
            top_pools['head'], top_pools['cape'], top_pools['back'], top_pools['chest'], 
            top_pools['hands'], top_pools['legs'], top_pools['feet'], 
            top_pools['neck'], top_pools['primary'], top_pools['secondary'], 
            top_pools['pet'], top_pools['tool'], top_pools['consumable']
        ]

        base_steps = activity.get('workRequired', 10)
        max_we = activity.get('maxWorkEfficiency', 1.0)
        base_xp = activity.get('xpRewards', {}).get(related_skill, 0) if related_skill else 0

        print(f"[{activity['name']}] Analisando combinações...")

        for combo in itertools.product(*simple_slots, ring_combos):
            # Achata a tupla de anéis dentro do combo
            full_combo = list(combo[:-1]) + list(combo[-1])
            gear_set = [item for item in full_combo if item is not None]
            
            # Validar Keywords (ex: A build TEM que ter o arco de caça)
            build_keywords = set()
            for item in gear_set:
                build_keywords.update(item['keywords'])
            
            if not required_keywords.issubset(build_keywords):
                continue # Combinação inválida, pula.

            # Somar os status
            tot_stats = {'we': 0.0, 'da': 0.0, 'dr': 0.0, 'nmc': 0.0, 'steps_flat': 0.0, 'steps_pct': 0.0, 'xp_pct': 0.0, 'xp_flat': 0.0}
            for item in gear_set:
                for k, v in item['stats'].items():
                    tot_stats[k] += v
            
            # Passa pra simulação real do jogo
            sim = self._evaluate_build(tot_stats, activity, player_level)
            
            metric = sim[objective]
            
            # Lógica de Min/Max baseada no objetivo
            is_better = (metric < best_metric_value) if objective == 'average_steps_per_action' else (metric > best_metric_value)
            
            if is_better:
                best_metric_value = metric
                best_build = {
                    'gear': gear_set,
                    'stats': sim
                }

        return best_build

    def _evaluate_build(self, build_stats, activity, player_level):
        we = build_stats.get('we', 0.0)
        da = min(build_stats.get('da', 0.0), 1.0)
        dr = build_stats.get('dr', 0.0)
        nmc = build_stats.get('nmc', 0.0)
        steps_flat = build_stats.get('steps_flat', 0.0)
        steps_pct = build_stats.get('steps_pct', 0.0)
        bxp_pct = build_stats.get('xp_pct', 0.0)
        bxp_flat = build_stats.get('xp_flat', 0.0)
        
        base_steps = activity.get('workRequired')
        max_eff = activity.get('maxWorkEfficiency', 1.0)
        
        related_skills = activity.get('relatedSkillsList') or activity.get('relatedSkills', [])
        main_skill = related_skills[0] if related_skills else None
        
        base_xp = activity.get('xpRewardsMap', {}).get(main_skill, 0)
        if not base_xp:
            base_xp = activity.get('xpRewards', {}).get(main_skill, 0)
            
        req_level = 1
        for req in (activity.get('requirements') or []):
            if req.get('type') == 'skillLevel' and req.get('requirement', {}).get('skill') == main_skill:
                req_level = req['requirement']['level']
                break
                
        # Só dá eficiência por nível se a atividade não for 'travelling'
        is_travelling = activity.get('id') == 'travelling'
        level_eff = 0.0 if is_travelling else min(max(player_level - req_level, 0) * 0.0125, 0.25)
        
        total_eff = min(1.0 + level_eff + we, max_eff)
        c = 1.0 + steps_pct
        l = steps_flat
        
        if base_steps:
            f = math.ceil((base_steps / total_eff) * c) + l
        else:
            f = 0
            
        p = max(10.0, float(f))
        final_steps = p / (1.0 + da)
        
        safe_nmc = min(nmc, 0.99)
        yield_multiplier = ((1.0 + da) * (1.0 + dr)) / (1.0 - safe_nmc)
        
        calc_xp = base_xp * (1.0 + bxp_pct) + bxp_flat
        effective_xp = calc_xp * (1.0 + da)
        
        return {
            "xp_per_step": effective_xp / final_steps if final_steps > 0 else 0,
            "yield_per_step": yield_multiplier / final_steps if final_steps > 0 else 0,
            "average_steps_per_action": final_steps
        }

    def _extract_item_stats(self, item, current_skill):
        """Varre os itemAttrs JSON e extrai apenas os status que afetam nossa skill atual."""
        extracted = {'we': 0.0, 'da': 0.0, 'dr': 0.0, 'nmc': 0.0, 'steps_flat': 0.0, 'steps_pct': 0.0, 'xp_pct': 0.0, 'xp_flat': 0.0}
        
        def parse_attrs(attrs_list):
            for attr in attrs_list:
                reqs = attr.get('requirements') or []
                valid_req = True
                for req in reqs:
                    if req.get('type') == 'mainSkill' and req['requirement']['skill'] != current_skill:
                        valid_req = False
                        break
                
                if not valid_req:
                    continue
                    
                for stat in (attr.get('stats') or []):
                    val = float(stat.get('value', 0.0))
                    
                    s_type = stat.get('type')
                    if s_type == 'workEfficiency':
                        extracted['we'] += val
                    elif s_type == 'doubleAction':
                        extracted['da'] += val
                    elif s_type == 'doubleRewards':
                        extracted['dr'] += val
                    elif s_type == 'noMaterialsConsumed':
                        extracted['nmc'] += val
                    elif s_type == 'stepsRequired':
                        if stat.get('isPercent'):
                            extracted['steps_pct'] += val
                        else:
                            extracted['steps_flat'] += int(val)
                    elif s_type == 'bonusExperience':
                        if stat.get('isPercent'):
                            extracted['xp_pct'] += val
                        else:
                            extracted['xp_flat'] += val

        # Analisa os atributos base e os de qualidade
        parse_attrs((item.get('itemAttrs') or []) + (item.get('itemQualityAttrs') or []))
        
        # Analisa os consumíveis (armazenados em buffs)
        for buff_tier in (item.get('buffs') or []):
            for data in (buff_tier.get('data') or []):
                for buff_obj in (data.get('buffs') or []):
                    parse_attrs((buff_obj.get('attributes') or []) + (buff_obj.get('fineAttributes') or []))
                    
        return extracted


if __name__ == "__main__":
    # Apenas como esqueleto de onde será chamado.
    # A testagem real exigirá importar o api_client e o user_parser.
    print("Módulo Otimizador carregado com sucesso.")