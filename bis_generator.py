import json
import time
from api_client import GameData
from optimizer import WalkscapeOptimizer

def get_relevant_items(original_items_map, activity, objective):
    """Extrai os atributos e retorna apenas os Top itens estritamente focados no objetivo."""
    def get_item_stats(item, act_skills):
        stats = {'we': 0.0, 'da': 0.0, 'steps_flat': 0.0, 'steps_pct': 0.0, 'xp': 0.0, 'dr': 0.0, 'nmc': 0.0}
        
        def parse_attrs(attrs_list):
            for attr in attrs_list:
                reqs = attr.get('requirements') or []
                valid = True
                for req in reqs:
                    if req.get('type') == 'mainSkill' and req['requirement'].get('skill') not in act_skills:
                        valid = False
                        break
                if not valid: continue
                
                for s in (attr.get('stats') or []):
                    val = s.get('value', 0)
                    if s.get('isNegative'): val = -val
                    
                    t = s.get('type')
                    if t == 'workEfficiency': stats['we'] += val
                    elif t == 'doubleAction': stats['da'] += val
                    elif t == 'doubleRewards': stats['dr'] += val
                    elif t == 'noMaterialsConsumed': stats['nmc'] += val
                    elif t == 'stepsRequired':
                        if s.get('isPercent'): stats['steps_pct'] -= val
                        else: stats['steps_flat'] -= val
                    elif t == 'bonusExperience': stats['xp'] += val

        parse_attrs((item.get('itemAttrs') or []) + (item.get('itemQualityAttrs') or []))
        
        for buff_tier in (item.get('buffs') or []):
            for data in (buff_tier.get('data') or []):
                for buff_obj in (data.get('buffs') or []):
                    parse_attrs((buff_obj.get('attributes') or []) + (buff_obj.get('fineAttributes') or []))
                    
        return stats

    act_skills = activity.get('relatedSkillsList') or activity.get('relatedSkills', [])
    act_keywords = set()
    # Coleta keywords que a atividade exige (ex: 'hunting_bow', 'fishing_net')
    for req in (activity.get('requirements') or []):
        if req.get('type') == 'keywordEquipped':
            act_keywords.add(req['requirement']['keyword'])
        elif req.get('type') == 'distinctKeywordItemsEquipped':
            for kw in req['requirement'].get('keywords', []):
                act_keywords.add(kw)
                
    # Agrupa itens por slot do corpo
    grouped = {}
    for item in original_items_map.values():
        g_type = item.get('gearType')
        if not g_type:
            if item.get('buffs') or item.get('type') == 'consumable': g_type = 'consumable'
            else: continue
        if g_type not in grouped: grouped[g_type] = []
        grouped[g_type].append(item)
        
    final_map = {}
    for g_type, items in grouped.items():
        scored_items = []
        for item in items:
            stats = get_item_stats(item, act_skills)
            item_kws = item.get('keywords') or []
            has_req_kw = any(kw in item_kws for kw in act_keywords)
            
            score = 0
            if objective == "xp_per_step":
                score = stats['xp_pct']*1000 + stats['xp_flat']*100 + stats['da']*100 + (-stats['steps_flat'])*50 + (-stats['steps_pct'])*50 + stats['we']*10
            elif objective == "yield_per_step":
                score = stats['dr']*1000 + stats['nmc']*1000 + stats['da']*100 + (-stats['steps_flat'])*50 + (-stats['steps_pct'])*50 + stats['we']*10
            elif objective == "average_steps_per_action":
                score = stats['da']*100 + (-stats['steps_flat'])*50 + (-stats['steps_pct'])*50 + stats['we']*10
            
            if has_req_kw:
                score += 1000000
                
            if score > 0:
                scored_items.append((score, item))
                
        # Ordena pelo score do maior para o menor
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        # Limita a quantidade para evitar explosão combinatória
        limit = 4 if g_type in ['ring', 'tool'] else 2
        
        kept = 0
        for score, item in scored_items:
            final_map[item['id']] = item
            kept += 1
            if kept >= limit:
                break
                        
    return final_map

def generate_all_bis():
    print("Carregando Dados da API...")
    game_data = GameData()
    
    # Inicializamos o otimizador sem 'user_data' porque queremos os itens de todo o jogo
    optimizer = WalkscapeOptimizer(game_data, user_data=None)
    
    # Fazemos um backup dos itens de todo o jogo na memória original
    original_items_map = game_data.items_map.copy()

    results = {}
    objectives = ["xp_per_step", "average_steps_per_action", "yield_per_step"]
    
    # Filtrando as atividades reais do jogo (ignoramos ids inválidos/vazios)
    valid_activities = [act for act in game_data.activities if act['id'] != 'none']
    valid_recipes = [rec for rec in getattr(game_data, 'recipes', []) if rec['id'] != 'none']
    all_tasks = valid_activities + valid_recipes
    total = len(all_tasks)
    
    bis_cache = {}
    global_start_time = time.time()
    print(f"Iniciando cálculo intensivo para {total} tarefas (atividades + receitas)...")
    
    for index, activity in enumerate(all_tasks, 1):
        act_start_time = time.time()
        act_id = activity['id']
        act_name = activity.get('name', act_id)
        print(f"[{index:03d}/{total}] Calculando BiS para: {act_name}")

        # Cria uma Assinatura Única para a atividade
        act_skills = tuple(sorted(activity.get('relatedSkillsList') or activity.get('relatedSkills', [])))
        act_kws = set()
        for req in (activity.get('requirements') or []):
            if req.get('type') == 'keywordEquipped':
                act_kws.add(req['requirement']['keyword'])
            elif req.get('type') == 'distinctKeywordItemsEquipped':
                for kw in req['requirement'].get('keywords', []):
                    act_kws.add(kw)
        act_kws = tuple(sorted(list(act_kws)))
        work_req = activity.get('workRequired', 10)
        
        signature = (act_skills, act_kws, work_req)

        results[act_id] = {
            "name": act_name,
            "objectives": {}
        }
        
        for obj in objectives:
            cache_key = (signature, obj)
            print(f"  -> Otimizando para o objetivo: {obj}...")
            
            if cache_key in bis_cache:
                print(f"     [Cache] Build recuperada! Mesmas restrições de uma atividade anterior.")
                results[act_id]["objectives"][obj] = bis_cache[cache_key]
                continue
                
            try:
                # Filtra APENAS para este objetivo específico!
                filtered_items = get_relevant_items(original_items_map, activity, obj)
                game_data.items_map = filtered_items
                print(f"     [Filtro] Itens reduzidos de {len(original_items_map)} para {len(filtered_items)} melhores peças.")
                
                # use_only_owned=False para garantir que ele teste TODOS os itens do jogo
                best_build = optimizer.optimize(act_id, obj, use_only_owned=False)
                
                if best_build:
                    # Mapeando os equipamentos de forma simplificada e legível para o JSON final
                    gear_summary = []
                    for item in best_build['gear']:
                        slot = game_data.items_map[item['id']].get('gearType')
                        if not slot:
                            slot = 'consumable' if game_data.items_map[item['id']].get('buffs') or game_data.items_map[item['id']].get('type') == 'consumable' else 'unknown'
                        gear_summary.append({
                            "slot": slot.capitalize(),
                            "id": item['id'],
                            "name": item['name']
                        })
                        
                    formatted_result = {
                        "metrics": best_build['stats'],
                        "equipment": gear_summary
                    }
                    results[act_id]["objectives"][obj] = formatted_result
                    bis_cache[cache_key] = formatted_result
                    
                    metric_val = best_build['stats'].get(obj, 0)
                    print(f"     [Sucesso] Build encontrada! {obj} = {metric_val:.4f}")
                else:
                    print(f"     [Aviso] Nenhuma build viável encontrada para este objetivo.")
                    results[act_id]["objectives"][obj] = None
            except Exception as e:
                print(f"  [!] Erro na atividade {act_name} ({obj}): {e}")
                results[act_id]["objectives"][obj] = None
                
        act_end_time = time.time()
        print(f"  [Concluído] Atividade finalizada em {act_end_time - act_start_time:.2f} segundos.\n")
                
    # Restaura o banco de dados pro estado original ao fim do script por segurança
    game_data.items_map = original_items_map

    output_file = "bis_export.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
        
    global_total_time = time.time() - global_start_time
    print(f"✅ Geração BiS concluída com sucesso! Tempo total: {global_total_time:.2f} segundos.")
        
if __name__ == "__main__":
    generate_all_bis()
