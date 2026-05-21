import json
import time
import multiprocessing
import concurrent.futures
import math
from api_client import GameData
from optimizer import WalkscapeOptimizer

def get_item_stats(item, act_skills):
    stats = {'we': 0.0, 'da': 0.0, 'steps_flat': 0.0, 'steps_pct': 0.0, 'xp': 0.0, 'dr': 0.0, 'nmc': 0.0, 'fmf': 0.0}
    
    skill_types = {
        'gathering': ['foraging', 'fishing', 'mining', 'woodcutting', 'hunting'],
        'artisan': ['carpentry', 'cooking', 'crafting', 'smithing', 'tailoring', 'trinketry'],
        'utility': ['agility', 'traveling']
    }

    def parse_attrs(attrs_list):
        for attr in attrs_list:
            reqs = attr.get('requirements') or []
            valid = True
            for req in reqs:
                req_type = req.get('type')
                if req_type == 'mainSkill' and req['requirement'].get('skill') not in act_skills:
                    valid = False
                    break
                elif req_type == 'mainSkillType':
                    req_skill_type = req['requirement'].get('type')
                    if not any(skill in skill_types.get(req_skill_type, []) for skill in act_skills):
                        valid = False
                        break
            if not valid: continue
            
            for s in (attr.get('stats') or []):
                val = float(s.get('value', 0.0))
                if s.get('isNegative') and val > 0:
                    val = -val
                
                t = s.get('type')
                if t == 'workEfficiency': stats['we'] += val
                elif t == 'doubleAction': stats['da'] += val
                elif t == 'doubleRewards': stats['dr'] += val
                elif t == 'noMaterialsConsumed': stats['nmc'] += val
                elif t == 'fineMaterialFind': stats['fmf'] += val
                elif t == 'stepsRequired':
                    if s.get('isPercent'): stats['steps_pct'] += val
                    else: stats['steps_flat'] += val
                elif t == 'bonusExperience': stats['xp'] += val

    parse_attrs((item.get('itemAttrs') or []) + (item.get('itemQualityAttrs') or []))
    
    for buff_tier in (item.get('buffs') or []):
        for data in (buff_tier.get('data') or []):
            for buff_obj in (data.get('buffs') or []):
                parse_attrs((buff_obj.get('attributes') or []) + (buff_obj.get('fineAttributes') or []))
                
    return stats

def get_relevant_items(original_items_map, activity, objective):
    """Extrai os atributos e retorna apenas os Top itens estritamente focados no objetivo."""
    
    act_skills = activity.get('relatedSkillsList') or activity.get('relatedSkills') or []
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
            if objective in ["lowest_steps_per_action", "average_steps_per_action"]:
                score = (-stats['steps_flat']) * 1000 + (-stats['steps_pct']) * 1000 + stats['we'] * 100 + stats['da'] * 50 + stats['dr'] * 10
            elif objective in ["highest_loot_per_step", "yield_per_step"]:
                score = stats['dr'] * 1000 + stats['nmc'] * 1000 + stats['da'] * 500 + (-stats['steps_flat']) * 500 + (-stats['steps_pct']) * 500 + stats['we'] * 50
            elif objective == "highest_fine_items_per_step":
                score = stats['fmf'] * 1000 + stats['da'] * 100 + (-stats['steps_flat']) * 500 + (-stats['steps_pct']) * 500 + stats['we'] * 50
            else:
                score = stats['xp'] * 1000 + stats['da'] * 100 + (-stats['steps_flat']) * 500 + (-stats['steps_pct']) * 500 + stats['we'] * 50
            
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

def optimize_worker(task_payload):
    signature, activity, objectives, original_items_map = task_payload
    
    # Instancia localmente para evitar concorrência e race conditions (já que alteramos items_map dinamicamente)
    local_game_data = GameData()
    local_optimizer = WalkscapeOptimizer(local_game_data, user_data=None)
    act_skills = activity.get('relatedSkillsList') or activity.get('relatedSkills') or []
    
    result_objectives = {}
    for obj in objectives:
        try:
            filtered_items = get_relevant_items(original_items_map, activity, obj)
            local_game_data.items_map = filtered_items
            
            best_build = local_optimizer.optimize(activity['id'], obj, use_only_owned=False)
            
            if best_build:
                gear_summary = []
                total_steps_flat = 0.0
                
                for item in best_build['gear']:
                    full_item = local_game_data.items_map.get(item['id'], {})
                    item_stats = get_item_stats(full_item, act_skills)
                    total_steps_flat += item_stats['steps_flat']
                    
                    slot = full_item.get('gearType')
                    if not slot:
                        slot = 'consumable' if full_item.get('buffs') or full_item.get('type') == 'consumable' else 'unknown'
                    gear_summary.append({
                        "slot": slot.capitalize(),
                        "id": item['id'],
                        "name": item['name']
                    })
                    
                result_objectives[obj] = {
                    "metrics": best_build['stats'],
                    "equipment": gear_summary
                }
            else:
                result_objectives[obj] = None
        except Exception as e:
            import traceback
            print(f"Erro no cálculo de {activity.get('id')} ({obj}): {e}")
            traceback.print_exc()
            result_objectives[obj] = None
            
    return signature, result_objectives

def generate_all_bis():
    print("Carregando Dados da API...")
    game_data = GameData()
    original_items_map = game_data.items_map.copy()

    results = {}
    objectives = ["lowest_steps_per_action", "highest_loot_per_step", "highest_fine_items_per_step"]
    
    valid_activities = [act for act in game_data.activities if act['id'] != 'none']
    valid_recipes = [rec for rec in getattr(game_data, 'recipes', []) if rec['id'] != 'none']
    all_tasks = valid_activities + valid_recipes
    total = len(all_tasks)
    
    global_start_time = time.time()
    
    # Agrupamento inteligente por assinatura para poupar cálculo duplicado
    unique_tasks = {}
    task_mapping = {}
    
    for index, activity in enumerate(all_tasks, 1):
        act_id = activity['id']
        act_name = activity.get('name', act_id)

        act_skills = tuple(sorted(activity.get('relatedSkillsList') or activity.get('relatedSkills') or []))
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
        task_mapping[act_id] = {
            "name": act_name,
            "signature": signature
        }
        
        if signature not in unique_tasks:
            unique_tasks[signature] = activity

    print(f"De {total} atividades/receitas, foram extraídas {len(unique_tasks)} assinaturas únicas para cálculo.")
    
    payloads = [(sig, act, objectives, original_items_map) for sig, act in unique_tasks.items()]
    bis_cache = {}
    
    workers = max(1, multiprocessing.cpu_count() - 1)
    print(f"Iniciando cálculo em paralelo usando {workers} processos...\n")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_sig = {executor.submit(optimize_worker, p): p[0] for p in payloads}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_sig):
            completed += 1
            sig = future_to_sig[future]
            try:
                res_sig, res_objs = future.result()
                bis_cache[res_sig] = res_objs
                print(f"[{completed:03d}/{len(unique_tasks)}] Assinatura calculada com sucesso.")
            except Exception as exc:
                print(f"[{completed:03d}/{len(unique_tasks)}] Erro no cálculo: {exc}")
                bis_cache[sig] = {obj: None for obj in objectives}

    # Remontar o JSON com os resultados espelhados
    for act_id, info in task_mapping.items():
        results[act_id] = {
            "name": info["name"],
            "objectives": bis_cache.get(info["signature"], {obj: None for obj in objectives})
        }

    output_file = "bis_export.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
        
    global_total_time = time.time() - global_start_time
    print(f"✅ Geração BiS concluída com sucesso! Tempo total: {global_total_time:.2f} segundos.")
        
if __name__ == "__main__":
    generate_all_bis()
