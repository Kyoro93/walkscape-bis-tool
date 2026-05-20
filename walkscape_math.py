import math

class WalkscapeMath:
    """
    Módulo central que replica a lógica matemática oficial do Walkscape,
    baseado nas funções Gp, d0 e f0 do frontend do jogo.
    """

    @staticmethod
    def calculate_level_we_bonus(player_level, required_level, is_travelling=False):
        """
        Calcula o bônus de Work Efficiency providenciado apenas pela diferença
        entre o nível atual do jogador e o nível exigido pela atividade.
        """
        diff = max(0, player_level - required_level)
        
        if is_travelling:
            # Para viagem, o bônus é 0.5% por nível acima, sem limite de nível
            return diff * 0.005
        else:
            # Para atividades normais, o bônus é 1.25% por nível acima, limitado a 20 níveis (+25% WE máximo)
            return min(diff, 20) * 0.0125

    @staticmethod
    def calculate_level_qo_bonus(player_level, required_level):
        """
        Calcula o bônus de Quality Outcome providenciado pela diferença
        de nível em atividades de Crafting.
        """
        return max(0, player_level - required_level)

    @staticmethod
    def calculate_action_stats(
        base_steps, 
        max_we_multiplier, 
        gear_we=0.0, 
        level_we_bonus=0.0, 
        flat_step_reduction=0, 
        percent_step_reduction=0.0,
        double_action_chance=0.0,
        base_xp=0.0,
        bonus_xp_percent=0.0,
        bonus_xp_flat=0.0
    ):
        """
        Calcula os passos e experiência gerados por uma única ação, aplicando
        os caps (limites) corretos do jogo.
        
        :param base_steps: Passos base exigidos (workRequired na API).
        :param max_we_multiplier: Teto máximo do WE (maxWorkEfficiency na API).
        :param percent_step_reduction: Redução % (vem como negativo da API, ex: -0.1 para 10%).
        :return: Um dicionário com as estatísticas simuladas.
        """
        # 1. Calcula a Eficiência de Trabalho atual
        # O jogo considera a base como 1 (100%) + WE dos equipamentos + WE do nível
        uncapped_we = 1.0 + gear_we + level_we_bonus
        
        # 2. Aplica a trava (Cap) de Eficiência
        capped_we = min(uncapped_we, max_we_multiplier)
        
        # 3. Calcula os passos brutos por ação
        # Fómula oficial: Math.ceil(workRequired / u * c) + l
        # Onde u = capped_we, c = (1 + percent_step_reduction) e l = flat_step_reduction
        c = 1.0 + percent_step_reduction
        uncapped_steps = math.ceil((base_steps / capped_we) * c) + flat_step_reduction
        
        # 4. Limite Mínimo Absoluto do Jogo: Nunca menos que 10 passos por ação
        steps_per_completion = max(10, uncapped_steps)
        
        # 5. Efeito da Ação Dupla (Double Action) no longo prazo
        # Double action chance é limitada a 100% (1.0). Corta efetivamente a média de passos.
        da_chance = min(1.0, double_action_chance)
        average_steps_per_action = steps_per_completion / (1.0 + da_chance)
        
        # 6. Cálculo da Experiência por Ação
        # Fómula: value = (1 + H) * (Me + D)
        xp_per_action = (1.0 + bonus_xp_percent) * (base_xp + bonus_xp_flat)
        
        # 7. A Grande Métrica: Experiência Média por Passo percorrido
        xp_per_step = xp_per_action / average_steps_per_action if average_steps_per_action > 0 else 0
        
        return {
            "uncapped_we": uncapped_we,
            "capped_we": capped_we,
            "is_we_capped": uncapped_we >= max_we_multiplier,
            "steps_per_completion": steps_per_completion,
            "average_steps_per_action": average_steps_per_action,
            "xp_per_action": xp_per_action,
            "xp_per_step": xp_per_step
        }

if __name__ == "__main__":
    # === TESTE DE MESA DO MÓDULO ===
    # Simulando um "Unicorn Hunting"
    print("Testando matemática do jogo para: Unicorn Hunting")
    stats = WalkscapeMath.calculate_action_stats(
        base_steps=600,             # Supondo 600 passos base
        max_we_multiplier=3.0,      # Supondo max 300%
        gear_we=0.75,               # +75% WE dos equipamentos
        level_we_bonus=0.25,        # Máximo de +25% do nível
        flat_step_reduction=-2,     # Cape of achiever (-2 passos)
        double_action_chance=0.05,  # 5% de Double Action (Anel)
        base_xp=45.0,               # XP Base
        bonus_xp_percent=0.26       # +26% bônus xp
    )
    
    for key, val in stats.items():
        if isinstance(val, float):
            print(f"{key}: {val:.4f}")
        else:
            print(f"{key}: {val}")
            