import sys
from collections import defaultdict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QComboBox, QCheckBox, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont
from PyQt6.QtCore import Qt

# Importando os nossos módulos
from api_client import GameData
from user_parser import UserData
from optimizer import WalkscapeOptimizer

class WalkscapeGearOptimizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Walkscape - Best in Slot Optimizer")
        self.resize(800, 700)
        
        # Inicializa Dados do Jogo e Dados do Usuário
        self.game_data = GameData()
        self.user_data = None
        
        self.init_ui()
        self.populate_activities()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # --- GRUPO 0: DADOS DA API ---
        api_group = QGroupBox("0. Banco de Dados da API")
        api_layout = QHBoxLayout()
        
        self.lbl_api_status = QLabel("API carregada na inicialização." if self.game_data.activities else "API ausente ou com erro.")
        self.lbl_api_status.setStyleSheet("color: green; font-weight: bold;" if self.game_data.activities else "color: red; font-weight: bold;")
        
        self.btn_reload_api = QPushButton("Recarregar JSONs da API")
        self.btn_reload_api.clicked.connect(self.reload_api)
        
        api_layout.addWidget(self.lbl_api_status, stretch=1)
        api_layout.addWidget(self.btn_reload_api)
        api_group.setLayout(api_layout)
        main_layout.addWidget(api_group)

        # --- GRUPO 1: IMPORTAR SAVE ---
        save_group = QGroupBox("1. Importar Save do Jogo (Opcional, mas recomendado)")
        save_layout = QVBoxLayout()
        
        self.txt_save = QTextEdit()
        self.txt_save.setPlaceholderText("Cole a string exportada do jogo aqui...")
        self.txt_save.setMaximumHeight(80)
        save_layout.addWidget(self.txt_save)
        
        self.btn_load_save = QPushButton("Carregar Inventário e Stats")
        self.btn_load_save.clicked.connect(self.load_save_data)
        save_layout.addWidget(self.btn_load_save)
        
        self.lbl_user_status = QLabel("Status: Nenhum save carregado.")
        self.lbl_user_status.setStyleSheet("color: gray;")
        save_layout.addWidget(self.lbl_user_status)
        
        save_group.setLayout(save_layout)
        main_layout.addWidget(save_group)
        
        # --- GRUPO 2: CONFIGURAÇÃO DE OTIMIZAÇÃO ---
        opt_group = QGroupBox("2. Configurar Otimização")
        opt_layout = QVBoxLayout()
        
        # Atividade
        row_activity = QHBoxLayout()
        row_activity.addWidget(QLabel("Atividade Alvo:"))
        
        self.cmb_activity = QComboBox()
        # Define um modelo padrão para podermos ter itens desabilitados (cabeçalhos)
        self.cmb_activity.setModel(QStandardItemModel())
        row_activity.addWidget(self.cmb_activity, stretch=1)
        opt_layout.addLayout(row_activity)
        
        # Objetivo
        row_objective = QHBoxLayout()
        row_objective.addWidget(QLabel("Objetivo principal:"))
        self.cmb_objective = QComboBox()
        self.cmb_objective.addItem("Máximo de XP por Passo", "xp_per_step")
        self.cmb_objective.addItem("Mínimo de Passos por Ação (Velocidade)", "average_steps_per_action")
        row_objective.addWidget(self.cmb_objective, stretch=1)
        opt_layout.addLayout(row_objective)
        
        # Checkbox Inventário
        self.chk_use_owned = QCheckBox("Calcular Best in Slot APENAS com itens que possuo")
        self.chk_use_owned.setChecked(False) # Padrão falso até carregar o save
        self.chk_use_owned.setEnabled(False) # Desabilitado até carregar o save
        opt_layout.addWidget(self.chk_use_owned)
        
        # Botão Otimizar
        self.btn_optimize = QPushButton("OTIMIZAR EQUIPAMENTO")
        self.btn_optimize.setMinimumHeight(40)
        self.btn_optimize.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.btn_optimize.clicked.connect(self.run_optimization)
        opt_layout.addWidget(self.btn_optimize)
        
        opt_group.setLayout(opt_layout)
        main_layout.addWidget(opt_group)
        
        # --- GRUPO 3: RESULTADOS ---
        res_group = QGroupBox("3. Equipamento Best in Slot")
        res_layout = QVBoxLayout()
        
        self.lbl_stats = QLabel("Simulação das métricas aparecerão aqui...")
        self.lbl_stats.setStyleSheet("font-weight: bold;")
        res_layout.addWidget(self.lbl_stats)
        
        self.table_results = QTableWidget(0, 3)
        self.table_results.setHorizontalHeaderLabels(["Slot", "Nome do Item", "Atributos Úteis"])
        self.table_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        res_layout.addWidget(self.table_results)
        
        res_group.setLayout(res_layout)
        main_layout.addWidget(res_group, stretch=1)

    def reload_api(self):
        """Recarrega os dados da API e atualiza a interface."""
        self.game_data = GameData()
        self.cmb_activity.model().clear()
        self.populate_activities()
        
        if self.game_data.activities:
            self.lbl_api_status.setText("API carregada com sucesso!")
            self.lbl_api_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_api_status.setText("Erro ao ler JSONs da API na pasta api_responses.")
            self.lbl_api_status.setStyleSheet("color: red; font-weight: bold;")

    def populate_activities(self):
        """Agrupa atividades por Skill e adiciona cabeçalhos visuais ao Combobox."""
        if not self.game_data.activities:
            QMessageBox.critical(self, "Erro", "Não foi possível carregar as atividades da API.")
            return
            
        # Agrupar
        skills_dict = defaultdict(list)
        for act in self.game_data.activities:
            # Evitar atividades sem nome ou de viagem simples caso não deseje otimizá-las
            if act['id'] == 'none': continue 
            
            skill = act.get('relatedSkillsList', ['Geral'])[0]
            if not skill: skill = 'Geral'
            skills_dict[skill].append(act)
            
        model = self.cmb_activity.model()
        
        for skill in sorted(skills_dict.keys()):
            # Cria um item de Cabeçalho (Não selecionável)
            header_item = QStandardItem(f"--- {skill.capitalize()} ---")
            header_item.setEnabled(False)
            header_item.setBackground(QColor("#e0e0e0"))
            header_font = QFont()
            header_font.setBold(True)
            header_item.setFont(header_font)
            header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            model.appendRow(header_item)
            
            # Adiciona as atividades desta skill ordenadas
            for act in sorted(skills_dict[skill], key=lambda x: x['name']):
                act_item = QStandardItem(f"  {act['name']}")
                act_item.setData(act['id']) # Guarda o ID no background
                model.appendRow(act_item)

    def load_save_data(self):
        save_str = self.txt_save.toPlainText()
        if not save_str:
            QMessageBox.warning(self, "Aviso", "Por favor, cole a string do save primeiro.")
            return
            
        self.user_data = UserData(save_str)
        if len(self.user_data.owned_base_items) > 0:
            self.lbl_user_status.setText(
                f"Status: Save carregado! Level {self.user_data.character_level} | "
                f"{len(self.user_data.owned_base_items)} itens únicos desbloqueados."
            )
            self.lbl_user_status.setStyleSheet("color: green; font-weight: bold;")
            # Habilita e marca a restrição de inventário por padrão
            self.chk_use_owned.setEnabled(True)
            self.chk_use_owned.setChecked(True)
            self.txt_save.clear() # Limpa a caixa por motivos de performance/visuais
        else:
            self.lbl_user_status.setText("Status: Erro ao ler o save. String inválida?")
            self.lbl_user_status.setStyleSheet("color: red;")
            self.user_data = None
            self.chk_use_owned.setEnabled(False)
            self.chk_use_owned.setChecked(False)

    def run_optimization(self):
        # Extrair o ID selecionado no Combobox (ignora cliques nos cabeçalhos se houver burla)
        current_index = self.cmb_activity.currentIndex()
        activity_id = self.cmb_activity.model().item(current_index).data()
        
        if not activity_id:
            return # Clicou em um cabeçalho
            
        objective = self.cmb_objective.currentData()
        use_only_owned = self.chk_use_owned.isChecked()
        
        if use_only_owned and not self.user_data:
            QMessageBox.warning(self, "Aviso", "Você escolheu usar itens do inventário, mas não carregou um save válido.")
            return
            
        self.lbl_stats.setText("Processando milhares de combinações...")
        QApplication.processEvents() # Força a interface a atualizar o texto
        
        # Motor de Otimização
        optimizer = WalkscapeOptimizer(self.game_data, self.user_data)
        
        try:
            best_build = optimizer.optimize(activity_id, objective, use_only_owned)
        except Exception as e:
            QMessageBox.critical(self, "Erro no Cálculo", str(e))
            return
            
        if not best_build:
            self.lbl_stats.setText("Nenhuma combinação válida encontrada (falta itens/keywords necessárias?)")
            self.table_results.setRowCount(0)
            return
            
        # Preencher os resultados
        stats = best_build['stats']
        self.lbl_stats.setText(
            f"Métricas Estimadas: XP/Passo: {stats['xp_per_step']:.2f}  |  "
            f"Média Passos/Ação: {stats['average_steps_per_action']:.1f}  |  "
            f"WE Atingida: {stats['capped_we']*100:.0f}% (Limite do Cap: {'Sim' if stats['is_we_capped'] else 'Não'})"
        )
        
        gear_list = best_build['gear']
        self.table_results.setRowCount(len(gear_list))
        for row, item in enumerate(gear_list):
            slot_type = self.game_data.items_map[item['id']].get('gearType', '').capitalize()
            self.table_results.setItem(row, 0, QTableWidgetItem(slot_type))
            self.table_results.setItem(row, 1, QTableWidgetItem(item['name']))
            
            # Formatar os status úteis
            s = item['stats']
            stat_strings = []
            if s['we'] != 0: stat_strings.append(f"WE: +{s['we']*100:.1f}%")
            if s['da'] != 0: stat_strings.append(f"DA: +{s['da']*100:.1f}%")
            if s['steps_flat'] != 0: stat_strings.append(f"Passos: {s['steps_flat']}")
            if s['steps_pct'] != 0: stat_strings.append(f"Passos %: {s['steps_pct']*100:.1f}%")
            if s['xp_pct'] != 0: stat_strings.append(f"XP: +{s['xp_pct']*100:.1f}%")
            
            self.table_results.setItem(row, 2, QTableWidgetItem(" | ".join(stat_strings)))
            
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Estilo básico opcional para deixar com cara de app mais escura (estilo Walkscape)
    app.setStyle("Fusion") 
    window = WalkscapeGearOptimizerApp()
    window.show()
    sys.exit(app.exec())