import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import sqlite3
import os

# Configuration de la page
st.set_page_config(
    page_title="OPCOPILOT v3.0 - SPIC Guadeloupe",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles CSS personnalisés
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e, #2ca02c);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        font-size: 2rem;
        font-weight: bold;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1f77b4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    
    .status-active { color: #28a745; font-weight: bold; }
    .status-pending { color: #ffc107; font-weight: bold; }
    .status-critical { color: #dc3545; font-weight: bold; }
    
    .timeline-container {
        background: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    .phase-card {
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
    }
    
    .phase-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        transform: translateY(-2px);
    }
    
    .sidebar-logo {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        margin-bottom: 1rem;
        color: white;
    }
    
    .clickable-row {
        cursor: pointer;
        transition: background-color 0.3s;
    }
    
    .clickable-row:hover {
        background-color: #f8f9fa;
    }
    
    .aco-card {
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .frein-alert {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
    
    .frein-critical {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Classes de données
@dataclass
class Phase:
    id: str
    nom: str
    date_debut: datetime
    date_fin: datetime
    couleur: str
    statut: str = "En attente"  # En attente, En cours, Terminé, Retard
    description: str = ""
    responsable: str = ""
    freins: List[str] = None
    
    def __post_init__(self):
        if self.freins is None:
            self.freins = []

@dataclass
class Operation:
    id: str
    nom: str
    type_operation: str  # OPP, VEFA, MANDATS_ETUDES, MANDATS_REALISATION, AMO
    aco_responsable: str
    date_creation: datetime
    date_debut: datetime
    date_fin_prevue: datetime
    budget: float
    statut: str = "Créée"
    phases: List[Phase] = None
    
    def __post_init__(self):
        if self.phases is None:
            self.phases = []

@dataclass
class ACO:
    nom: str
    email: str
    telephone: str
    specialites: List[str]
    operations_en_cours: int = 0
    total_budget: float = 0.0

class DatabaseManager:
    def __init__(self, db_path="opcopilot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY,
                nom TEXT NOT NULL,
                type_operation TEXT NOT NULL,
                aco_responsable TEXT NOT NULL,
                date_creation TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin_prevue TEXT NOT NULL,
                budget REAL NOT NULL,
                statut TEXT DEFAULT 'Créée'
            )
        """)
        
        # Table phases
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phases (
                id TEXT PRIMARY KEY,
                operation_id TEXT NOT NULL,
                nom TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT NOT NULL,
                couleur TEXT NOT NULL,
                statut TEXT DEFAULT 'En attente',
                description TEXT,
                responsable TEXT,
                freins TEXT,
                FOREIGN KEY (operation_id) REFERENCES operations (id)
            )
        """)
        
        # Table ACO
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aco (
                nom TEXT PRIMARY KEY,
                email TEXT,
                telephone TEXT,
                specialites TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
        # Initialiser ACO par défaut
        self.init_default_aco()
    
    def init_default_aco(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM aco")
        count = cursor.fetchone()[0]
        
        if count == 0:
            default_aco = [
                ("Jean MARTIN", "j.martin@spic-guadeloupe.fr", "0590 12 34 56", json.dumps(["OPP", "VEFA"])),
                ("Marie DUBOIS", "m.dubois@spic-guadeloupe.fr", "0590 12 34 57", json.dumps(["MANDATS_ETUDES", "AMO"])),
                ("Pierre BERNARD", "p.bernard@spic-guadeloupe.fr", "0590 12 34 58", json.dumps(["MANDATS_REALISATION", "OPP"])),
                ("Sophie LEROY", "s.leroy@spic-guadeloupe.fr", "0590 12 34 59", json.dumps(["VEFA", "AMO"])),
                ("Michel PETIT", "m.petit@spic-guadeloupe.fr", "0590 12 34 60", json.dumps(["OPP", "MANDATS_ETUDES"]))
            ]
            
            cursor.executemany("INSERT INTO aco VALUES (?, ?, ?, ?)", default_aco)
            conn.commit()
        
        conn.close()
    
    def save_operation(self, operation: Operation):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO operations 
            (id, nom, type_operation, aco_responsable, date_creation, date_debut, date_fin_prevue, budget, statut)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            operation.id, operation.nom, operation.type_operation, operation.aco_responsable,
            operation.date_creation.isoformat(), operation.date_debut.isoformat(),
            operation.date_fin_prevue.isoformat(), operation.budget, operation.statut
        ))
        
        # Supprimer anciennes phases
        cursor.execute("DELETE FROM phases WHERE operation_id = ?", (operation.id,))
        
        # Insérer nouvelles phases
        for phase in operation.phases:
            cursor.execute("""
                INSERT INTO phases 
                (id, operation_id, nom, date_debut, date_fin, couleur, statut, description, responsable, freins)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                phase.id, operation.id, phase.nom, phase.date_debut.isoformat(),
                phase.date_fin.isoformat(), phase.couleur, phase.statut,
                phase.description, phase.responsable, json.dumps(phase.freins)
            ))
        
        conn.commit()
        conn.close()
    
    def load_operations(self) -> List[Operation]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM operations")
        operations_data = cursor.fetchall()
        
        operations = []
        for op_data in operations_data:
            # Charger les phases
            cursor.execute("SELECT * FROM phases WHERE operation_id = ? ORDER BY date_debut", (op_data[0],))
            phases_data = cursor.fetchall()
            
            phases = []
            for phase_data in phases_data:
                phase = Phase(
                    id=phase_data[0],
                    nom=phase_data[2],
                    date_debut=datetime.fromisoformat(phase_data[3]),
                    date_fin=datetime.fromisoformat(phase_data[4]),
                    couleur=phase_data[5],
                    statut=phase_data[6],
                    description=phase_data[7] or "",
                    responsable=phase_data[8] or "",
                    freins=json.loads(phase_data[9] or "[]")
                )
                phases.append(phase)
            
            operation = Operation(
                id=op_data[0],
                nom=op_data[1],
                type_operation=op_data[2],
                aco_responsable=op_data[3],
                date_creation=datetime.fromisoformat(op_data[4]),
                date_debut=datetime.fromisoformat(op_data[5]),
                date_fin_prevue=datetime.fromisoformat(op_data[6]),
                budget=op_data[7],
                statut=op_data[8],
                phases=phases
            )
            operations.append(operation)
        
        conn.close()
        return operations
    
    def load_aco(self) -> List[ACO]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM aco")
        aco_data = cursor.fetchall()
        
        operations = self.load_operations()
        
        aco_list = []
        for aco_record in aco_data:
            # Calculer statistiques pour cet ACO
            aco_operations = [op for op in operations if op.aco_responsable == aco_record[0]]
            operations_en_cours = len([op for op in aco_operations if op.statut in ["En cours", "Créée"]])
            total_budget = sum(op.budget for op in aco_operations)
            
            aco = ACO(
                nom=aco_record[0],
                email=aco_record[1],
                telephone=aco_record[2],
                specialites=json.loads(aco_record[3]),
                operations_en_cours=operations_en_cours,
                total_budget=total_budget
            )
            aco_list.append(aco)
        
        conn.close()
        return aco_list

# ===== TEMPLATES MÉTIER EXACTS CORRIGÉS (100+ PHASES AUTORISÉES) =====
TEMPLATES_PHASES = {
    # ===== OPP COMPLET (45 phases) =====
    "OPP": [
        # Phase identification et faisabilité
        {"nom": "Opportunité foncière identifiée", "duree_jours": 7, "couleur": "#2ca02c"},
        {"nom": "Faisabilité technique et financière", "duree_jours": 30, "couleur": "#2ca02c"},
        {"nom": "Validation programme", "duree_jours": 15, "couleur": "#2ca02c"},
        {"nom": "Acquisition foncier", "duree_jours": 90, "couleur": "#1f77b4"},
        {"nom": "Études géotechniques", "duree_jours": 30, "couleur": "#1f77b4"},
        {"nom": "Levée topographique", "duree_jours": 15, "couleur": "#1f77b4"},
        {"nom": "Étude environnementale", "duree_jours": 45, "couleur": "#1f77b4"},
        {"nom": "Consultation architecte", "duree_jours": 30, "couleur": "#ff7f0e"},
        {"nom": "Attribution marché MOE", "duree_jours": 15, "couleur": "#ff7f0e"},
        {"nom": "Notification MOE", "duree_jours": 7, "couleur": "#ff7f0e"},
        
        # Phase conception
        {"nom": "Phase ESQ (Esquisse)", "duree_jours": 30, "couleur": "#9467bd"},
        {"nom": "Phase APS (Avant-Projet Sommaire)", "duree_jours": 45, "couleur": "#9467bd"},
        {"nom": "Phase APD (Avant-Projet Définitif)", "duree_jours": 60, "couleur": "#9467bd"},
        {"nom": "Dépôt Permis de Construire", "duree_jours": 7, "couleur": "#d62728"},
        {"nom": "Instruction PC", "duree_jours": 120, "couleur": "#d62728"},
        {"nom": "Obtention PC", "duree_jours": 15, "couleur": "#d62728"},
        {"nom": "Purge recours PC", "duree_jours": 60, "couleur": "#d62728"},
        {"nom": "Phase PRO (Projet)", "duree_jours": 60, "couleur": "#8c564b"},
        {"nom": "Préparation DCE", "duree_jours": 30, "couleur": "#8c564b"},
        {"nom": "Consultation SPS", "duree_jours": 30, "couleur": "#8c564b"},
        
        # Phase consultation entreprises
        {"nom": "Lancement consultation entreprises", "duree_jours": 7, "couleur": "#e377c2"},
        {"nom": "Analyse offres", "duree_jours": 30, "couleur": "#e377c2"},
        {"nom": "Attribution marchés travaux", "duree_jours": 20, "couleur": "#e377c2"},
        {"nom": "Signature marchés", "duree_jours": 15, "couleur": "#e377c2"},
        {"nom": "Préparation chantier", "duree_jours": 30, "couleur": "#7f7f7f"},
        {"nom": "Installation chantier", "duree_jours": 10, "couleur": "#7f7f7f"},
        {"nom": "Ordre de service", "duree_jours": 3, "couleur": "#7f7f7f"},
        
        # Phase travaux
        {"nom": "Travaux VRD", "duree_jours": 60, "couleur": "#bcbd22"},
        {"nom": "Travaux terrassement", "duree_jours": 30, "couleur": "#bcbd22"},
        {"nom": "Travaux fondations", "duree_jours": 45, "couleur": "#bcbd22"},
        {"nom": "Travaux gros œuvre", "duree_jours": 120, "couleur": "#17becf"},
        {"nom": "Travaux étanchéité", "duree_jours": 30, "couleur": "#17becf"},
        {"nom": "Travaux charpente", "duree_jours": 45, "couleur": "#17becf"},
        {"nom": "Travaux couverture", "duree_jours": 30, "couleur": "#17becf"},
        {"nom": "Travaux cloisons", "duree_jours": 45, "couleur": "#aec7e8"},
        {"nom": "Travaux électricité", "duree_jours": 60, "couleur": "#aec7e8"},
        {"nom": "Travaux plomberie", "duree_jours": 60, "couleur": "#aec7e8"},
        {"nom": "Travaux climatisation", "duree_jours": 45, "couleur": "#aec7e8"},
        {"nom": "Travaux revêtements", "duree_jours": 60, "couleur": "#ffbb78"},
        {"nom": "Travaux peinture", "duree_jours": 45, "couleur": "#ffbb78"},
        {"nom": "Travaux menuiseries", "duree_jours": 30, "couleur": "#ffbb78"},
        
        # Phase raccordements
        {"nom": "Raccordement EDF", "duree_jours": 45, "couleur": "#98df8a"},
        {"nom": "Raccordement eau", "duree_jours": 30, "couleur": "#98df8a"},
        {"nom": "Raccordement fibre", "duree_jours": 20, "couleur": "#98df8a"},
        {"nom": "Raccordement assainissement", "duree_jours": 30, "couleur": "#98df8a"},
        {"nom": "Nettoyage final", "duree_jours": 10, "couleur": "#ff9896"}
    ],
    
    # ===== VEFA COMPLET (25 phases) =====
    "VEFA": [
        {"nom": "Recherche programmes VEFA", "duree_jours": 30, "couleur": "#2ca02c"},
        {"nom": "Analyse promoteurs", "duree_jours": 20, "couleur": "#2ca02c"},
        {"nom": "Négociation conditions", "duree_jours": 30, "couleur": "#2ca02c"},
        {"nom": "Due diligence technique", "duree_jours": 15, "couleur": "#1f77b4"},
        {"nom": "Due diligence juridique", "duree_jours": 15, "couleur": "#1f77b4"},
        {"nom": "Due diligence financière", "duree_jours": 10, "couleur": "#1f77b4"},
        {"nom": "Validation interne SPIC", "duree_jours": 15, "couleur": "#ff7f0e"},
        {"nom": "Signature contrat VEFA", "duree_jours": 7, "couleur": "#ff7f0e"},
        {"nom": "Appel de fonds 1 (35%)", "duree_jours": 3, "couleur": "#ff7f0e"},
        {"nom": "Suivi travaux fondations", "duree_jours": 60, "couleur": "#d62728"},
        {"nom": "Suivi travaux gros œuvre", "duree_jours": 120, "couleur": "#d62728"},
        {"nom": "Appel de fonds 2 (70%)", "duree_jours": 3, "couleur": "#d62728"},
        {"nom": "Suivi travaux second œuvre", "duree_jours": 90, "couleur": "#9467bd"},
        {"nom": "Suivi travaux finitions", "duree_jours": 60, "couleur": "#9467bd"},
        {"nom": "Suivi raccordements", "duree_jours": 30, "couleur": "#9467bd"},
        {"nom": "Pré-visite SPIC", "duree_jours": 7, "couleur": "#8c564b"},
        {"nom": "Pré-réception promoteur", "duree_jours": 15, "couleur": "#8c564b"},
        {"nom": "Levée réserves", "duree_jours": 60, "couleur": "#8c564b"},
        {"nom": "Réception définitive", "duree_jours": 7, "couleur": "#bcbd22"},
        {"nom": "Appel de fonds final (95%)", "duree_jours": 3, "couleur": "#bcbd22"},
        {"nom": "Remise clés", "duree_jours": 3, "couleur": "#bcbd22"},
        {"nom": "Livraison locataires", "duree_jours": 30, "couleur": "#17becf"},
        {"nom": "Solde final (5%)", "duree_jours": 7, "couleur": "#17becf"},
        {"nom": "DGD VEFA", "duree_jours": 30, "couleur": "#17becf"},
        {"nom": "Bilan opération VEFA", "duree_jours": 15, "couleur": "#17becf"}
    ],
    
    # ===== MANDATS_ETUDES EXACT (14 phases) =====
    "MANDATS_ETUDES": [
        {"nom": "Signature convention mandat", "duree_jours": 7, "couleur": "#2ca02c"},
        {"nom": "Définition besoins/programme", "duree_jours": 20, "couleur": "#2ca02c"},
        {"nom": "Diagnostic technique/urbain", "duree_jours": 30, "couleur": "#1f77b4"},
        {"nom": "Études de faisabilité", "duree_jours": 45, "couleur": "#1f77b4"},
        {"nom": "Lancement consultation programmiste", "duree_jours": 15, "couleur": "#ff7f0e"},
        {"nom": "Attribution/notification programmiste", "duree_jours": 10, "couleur": "#ff7f0e"},
        {"nom": "Lancement consultation MOE urbaine", "duree_jours": 20, "couleur": "#d62728"},
        {"nom": "Attribution/notification MOE urbaine", "duree_jours": 15, "couleur": "#d62728"},
        {"nom": "Démarrage études (OS)", "duree_jours": 5, "couleur": "#9467bd"},
        {"nom": "Concertation/validation intermédiaire", "duree_jours": 30, "couleur": "#9467bd"},
        {"nom": "Remise livrables intermédiaires", "duree_jours": 15, "couleur": "#8c564b"},
        {"nom": "Remise livrables finaux", "duree_jours": 20, "couleur": "#8c564b"},
        {"nom": "Validation mandant", "duree_jours": 15, "couleur": "#bcbd22"},
        {"nom": "Clôture mandat", "duree_jours": 10, "couleur": "#17becf"}
    ],
    
    # ===== MANDATS_REALISATION EXACT (21 phases) =====
    "MANDATS_REALISATION": [
        {"nom": "Signature convention mandat", "duree_jours": 7, "couleur": "#2ca02c"},
        {"nom": "Lancement consultation MOE", "duree_jours": 30, "couleur": "#2ca02c"},
        {"nom": "Attribution/notification MOE", "duree_jours": 15, "couleur": "#2ca02c"},
        {"nom": "OS études conception", "duree_jours": 5, "couleur": "#1f77b4"},
        {"nom": "Phase DIAG (si rénovation)", "duree_jours": 20, "couleur": "#1f77b4"},
        {"nom": "Phase ESQ (Esquisse)", "duree_jours": 30, "couleur": "#1f77b4"},
        {"nom": "Phase APS (Avant-Projet Sommaire)", "duree_jours": 45, "couleur": "#ff7f0e"},
        {"nom": "Phase APD (Avant-Projet Définitif)", "duree_jours": 60, "couleur": "#ff7f0e"},
        {"nom": "Phase PRO-DCE (Projet-DCE)", "duree_jours": 45, "couleur": "#ff7f0e"},
        {"nom": "Lancement consultation entreprises", "duree_jours": 30, "couleur": "#d62728"},
        {"nom": "Attribution/notification marchés", "duree_jours": 20, "couleur": "#d62728"},
        {"nom": "OS travaux", "duree_jours": 5, "couleur": "#d62728"},
        {"nom": "Phase EXE (Études exécution)", "duree_jours": 30, "couleur": "#9467bd"},
        {"nom": "Démarrage travaux", "duree_jours": 10, "couleur": "#9467bd"},
        {"nom": "Suivi chantier", "duree_jours": 240, "couleur": "#9467bd"},
        {"nom": "Réception provisoire", "duree_jours": 15, "couleur": "#8c564b"},
        {"nom": "Levée réserves", "duree_jours": 60, "couleur": "#8c564b"},
        {"nom": "Réception définitive", "duree_jours": 15, "couleur": "#8c564b"},
        {"nom": "DGD (Décompte Général)", "duree_jours": 30, "couleur": "#bcbd22"},
        {"nom": "GPA (Garantie Parfait Achèvement)", "duree_jours": 365, "couleur": "#bcbd22"},
        {"nom": "Clôture mandat", "duree_jours": 15, "couleur": "#17becf"}
    ],
    
    # ===== AMO EXACT (15 phases) =====
    "AMO": [
        {"nom": "Signature marché AMO", "duree_jours": 7, "couleur": "#2ca02c"},
        {"nom": "Assistance définition besoins", "duree_jours": 30, "couleur": "#2ca02c"},
        {"nom": "Assistance retenir MOE", "duree_jours": 45, "couleur": "#2ca02c"},
        {"nom": "Suivi études conception", "duree_jours": 120, "couleur": "#1f77b4"},
        {"nom": "Assistance rédaction pièces", "duree_jours": 30, "couleur": "#1f77b4"},
        {"nom": "Assistance retenir OPC/CT/SPS", "duree_jours": 20, "couleur": "#ff7f0e"},
        {"nom": "Assistance marchés entreprises", "duree_jours": 60, "couleur": "#ff7f0e"},
        {"nom": "Suivi exécution travaux", "duree_jours": 240, "couleur": "#d62728"},
        {"nom": "Assistance réceptions", "duree_jours": 30, "couleur": "#d62728"},
        {"nom": "Assistance DGD", "duree_jours": 45, "couleur": "#9467bd"},
        {"nom": "Suivi GPA", "duree_jours": 365, "couleur": "#9467bd"},
        {"nom": "Assistance clôture", "duree_jours": 20, "couleur": "#8c564b"},
        {"nom": "Bilan mission AMO", "duree_jours": 15, "couleur": "#8c564b"},
        {"nom": "Retour d'expérience", "duree_jours": 10, "couleur": "#bcbd22"},
        {"nom": "Clôture mission", "duree_jours": 5, "couleur": "#17becf"}
    ]
}

# ===== UNITÉS DE DURÉE MULTIPLES =====
UNITES_DUREE = {
    "jours": 1,
    "semaines": 7,
    "mois": 30
}

def convert_to_days(valeur: int, unite: str) -> int:
    """Convertit une durée en jours selon l'unité"""
    return valeur * UNITES_DUREE[unite]

def format_duration(jours: int) -> str:
    """Formate une durée en jours vers l'unité la plus appropriée"""
    if jours >= 30 and jours % 30 == 0:
        return f"{jours // 30} mois"
    elif jours >= 7 and jours % 7 == 0:
        return f"{jours // 7} semaines"
    else:
        return f"{jours} jours"

# Initialisation de la base de données
@st.cache_resource
def get_database():
    return DatabaseManager()

# Session state pour la navigation
if 'selected_operation_id' not in st.session_state:
    st.session_state.selected_operation_id = None
if 'selected_aco' not in st.session_state:
    st.session_state.selected_aco = None

def create_timeline_gantt(operation: Operation):
    """Crée une timeline Gantt horizontale avec flèches colorées - SYNCHRONISÉE"""
    if not operation.phases:
        st.warning("Aucune phase définie pour cette opération")
        return None
    
    fig = go.Figure()
    
    # Créer les barres pour chaque phase
    for i, phase in enumerate(operation.phases):
        # Calculer la durée en jours
        duration = (phase.date_fin - phase.date_debut).days + 1
        
        # Couleur selon le statut
        color = phase.couleur
        if phase.statut == "Terminé":
            color = "#28a745"
        elif phase.statut == "En cours":
            color = "#007bff"
        elif phase.statut == "Retard":
            color = "#dc3545"
        
        # Icône freins
        icon = " ⚠️" if phase.freins else ""
        
        # Ajouter la barre de la phase
        fig.add_trace(go.Bar(
            name=phase.nom,
            x=[duration],
            y=[f"{phase.nom}{icon}"],
            orientation='h',
            marker=dict(
                color=color,
                line=dict(color='white', width=2),
                opacity=0.9
            ),
            base=phase.date_debut,
            text=f"{format_duration(duration)}",
            textposition="inside",
            textfont=dict(color="white", size=10, family="Arial"),
            hovertemplate=(
                f"<b>{phase.nom}</b><br>"
                f"Début: {phase.date_debut.strftime('%d/%m/%Y')}<br>"
                f"Fin: {phase.date_fin.strftime('%d/%m/%Y')}<br>"
                f"Durée: {format_duration(duration)}<br>"
                f"Statut: {phase.statut}<br>"
                f"Responsable: {phase.responsable}<br>"
                f"Freins: {len(phase.freins)}<br>"
                "<extra></extra>"
            )
        ))
        
        # Ajouter une flèche si ce n'est pas la dernière phase
        if i < len(operation.phases) - 1:
            next_phase = operation.phases[i + 1]
            
            # Flèche de liaison
            fig.add_annotation(
                x=phase.date_fin,
                y=i,
                ax=next_phase.date_debut,
                ay=i + 1,
                arrowhead=2,
                arrowsize=1.5,
                arrowwidth=3,
                arrowcolor="#666666"
            )
    
    # Configuration du layout
    fig.update_layout(
        title={
            'text': f"Timeline Interactive - {operation.nom}",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#1f77b4'}
        },
        xaxis_title="Période",
        yaxis_title="Phases",
        height=max(400, len(operation.phases) * 40),
        showlegend=False,
        plot_bgcolor='rgba(248,249,250,0.8)',
        paper_bgcolor='rgba(255,255,255,1)',
        xaxis=dict(
            type='date',
            tickformat='%b %Y',
            gridcolor='lightgray',
            gridwidth=0.5,
            showgrid=True
        ),
        yaxis=dict(
            gridcolor='lightgray',
            gridwidth=0.5,
            showgrid=True,
            autorange="reversed"
        ),
        margin=dict(l=250, r=50, t=60, b=50),
        font=dict(family="Arial", size=11)
    )
    
    return fig

def dashboard():
    """Dashboard principal avec KPIs et vue d'ensemble - INTERACTIF"""
    st.markdown('<div class="main-header">🏗️ OPCOPILOT v3.0 - SPIC Guadeloupe</div>', unsafe_allow_html=True)
    
    db = get_database()
    operations = db.load_operations()
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📊 Opérations Totales",
            value=len(operations),
            delta=f"+{len([op for op in operations if op.date_creation > datetime.now() - timedelta(days=30)])} ce mois"
        )
    
    with col2:
        operations_actives = [op for op in operations if op.statut in ["En cours", "Créée"]]
        st.metric(
            label="🔄 Opérations Actives",
            value=len(operations_actives),
            delta=f"{len(operations_actives)/len(operations)*100:.1f}%" if operations else "0%"
        )
    
    with col3:
        budget_total = sum(op.budget for op in operations)
        st.metric(
            label="💰 Budget Total",
            value=f"{budget_total:,.0f} €",
            delta=f"{budget_total/len(operations):,.0f} € moy." if operations else "0 €"
        )
    
    with col4:
        phases_en_retard = sum(1 for op in operations for phase in op.phases if phase.statut == "Retard")
        freins_critiques = sum(1 for op in operations for phase in op.phases if phase.freins)
        st.metric(
            label="⚠️ Alertes Critiques",
            value=phases_en_retard + freins_critiques,
            delta="Action requise" if (phases_en_retard + freins_critiques) > 0 else "RAS",
            delta_color="inverse"
        )
    
    # Graphiques de suivi avec filtres
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Répartition par Type d'Opération")
        if operations:
            type_counts = {}
            for op in operations:
                type_counts[op.type_operation] = type_counts.get(op.type_operation, 0) + 1
            
            fig_pie = px.pie(
                values=list(type_counts.values()),
                names=list(type_counts.keys()),
                color_discrete_sequence=['#2ca02c', '#1f77b4', '#ff7f0e', '#d62728', '#9467bd']
            )
            fig_pie.update_layout(height=300)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Aucune opération créée")
    
    with col2:
        st.subheader("📊 KPIs par ACO")
        if operations:
            aco_stats = {}
            for op in operations:
                if op.aco_responsable not in aco_stats:
                    aco_stats[op.aco_responsable] = {"total": 0, "actives": 0, "budget": 0}
                aco_stats[op.aco_responsable]["total"] += 1
                aco_stats[op.aco_responsable]["budget"] += op.budget
                if op.statut in ["En cours", "Créée"]:
                    aco_stats[op.aco_responsable]["actives"] += 1
            
            df_aco = pd.DataFrame.from_dict(aco_stats, orient='index')
            df_aco['ACO'] = df_aco.index
            
            fig_bar = px.bar(
                df_aco, 
                x='ACO', 
                y='actives',
                title="Opérations Actives par ACO",
                color='actives',
                color_continuous_scale='Blues'
            )
            fig_bar.update_layout(height=300)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Aucune donnée ACO")
    
    # ===== TABLEAU INTERACTIF AVEC LIENS CLIQUABLES =====
    st.subheader("📋 Opérations Récentes (Cliquables)")
    if operations:
        # Trier par date de création (plus récentes d'abord)
        operations_sorted = sorted(operations, key=lambda x: x.date_creation, reverse=True)
        
        # Prendre les 10 plus récentes
        recent_ops = operations_sorted[:10]
        
        # Créer le DataFrame pour l'affichage
        data = []
        for op in recent_ops:
            phases_count = len(op.phases)
            phases_completed = len([p for p in op.phases if p.statut == "Terminé"])
            phases_retard = len([p for p in op.phases if p.statut == "Retard"])
            progress = f"{phases_completed}/{phases_count}" if phases_count > 0 else "0/0"
            
            # Indicateur de statut
            status_indicator = "🟢" if phases_retard == 0 else "🔴"
            if any(p.freins for p in op.phases):
                status_indicator = "🟠"
            
            data.append({
                "🎯": status_indicator,
                "Nom": op.nom,
                "Type": op.type_operation,
                "ACO": op.aco_responsable,
                "Statut": op.statut,
                "Budget": f"{op.budget:,.0f} €",
                "Progression": progress,
                "Créée le": op.date_creation.strftime("%d/%m/%Y"),
                "ID": op.id  # Caché pour sélection
            })
        
        df = pd.DataFrame(data)
        
        # Sélection d'opération avec callback
        event = st.dataframe(
            df.drop('ID', axis=1), 
            use_container_width=True, 
            height=400,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Navigation vers l'opération sélectionnée
        if event.selection and event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_op_id = df.iloc[selected_idx]['ID']
            st.session_state.selected_operation_id = selected_op_id
            st.success(f"✅ Opération '{df.iloc[selected_idx]['Nom']}' sélectionnée. Allez dans 'Opérations en cours' pour voir les détails.")
    else:
        st.info("Aucune opération trouvée. Utilisez le module 'Nouvelle Opération' pour commencer.")
    
    # Alertes et notifications avec actions
    st.subheader("🚨 Alertes & Notifications")
    
    alerts = []
    for op in operations:
        for phase in op.phases:
            if phase.statut == "Retard":
                alerts.append({
                    "type": "retard",
                    "message": f"⚠️ **{op.nom}** - Phase '{phase.nom}' en retard",
                    "operation_id": op.id
                })
            if phase.freins:
                alerts.append({
                    "type": "frein",
                    "message": f"🛑 **{op.nom}** - {len(phase.freins)} frein(s) sur '{phase.nom}'",
                    "operation_id": op.id
                })
    
    if alerts:
        for i, alert in enumerate(alerts[:5]):  # Afficher max 5 alertes
            col_alert, col_action = st.columns([3, 1])
            with col_alert:
                if alert["type"] == "retard":
                    st.error(alert["message"])
                else:
                    st.warning(alert["message"])
            with col_action:
                if st.button("Voir", key=f"alert_{i}"):
                    st.session_state.selected_operation_id = alert["operation_id"]
                    st.info("Allez dans 'Opérations en cours' pour traiter l'alerte.")
    else:
        st.success("✅ Aucune alerte critique")

def nouvelle_operation():
    """Module de création d'une nouvelle opération - AVEC DURÉES MULTIPLES"""
    st.header("➕ Nouvelle Opération")
    
    db = get_database()
    aco_list = db.load_aco()
    aco_names = [aco.nom for aco in aco_list]
    
    with st.form("nouvelle_operation"):
        col1, col2 = st.columns(2)
        
        with col1:
            nom = st.text_input("Nom de l'opération *", placeholder="Ex: Résidence Les Flamboyants")
            type_operation = st.selectbox(
                "Type d'opération *",
                ["OPP", "VEFA", "MANDATS_ETUDES", "MANDATS_REALISATION", "AMO"]
            )
            aco_responsable = st.selectbox("ACO Responsable *", aco_names)
        
        with col2:
            budget = st.number_input("Budget (€) *", min_value=0.0, value=500000.0, step=10000.0)
            date_debut = st.date_input("Date de début *", datetime.now().date())
            date_fin = st.date_input("Date de fin prévue *", (datetime.now() + timedelta(days=365)).date())
        
        # Configuration des phases avec templates complets
        st.subheader("🎯 Configuration des Phases")
        
        # Phases par défaut selon le type
        if type_operation in TEMPLATES_PHASES:
            template_phases = TEMPLATES_PHASES[type_operation]
            duree_totale = sum(p["duree_jours"] for p in template_phases)
            st.info(f"📋 Template **{type_operation}** : {len(template_phases)} phases - Durée totale : {format_duration(duree_totale)}")
            
            # Afficher les phases du template
            with st.expander(f"👁️ Voir les {len(template_phases)} phases du template {type_operation}"):
                for i, phase_template in enumerate(template_phases):
                    duration_formatted = format_duration(phase_template['duree_jours'])
                    st.write(f"**{i+1}.** {phase_template['nom']} - *{duration_formatted}*")
        
        # ===== OPTION PERSONNALISATION AVEC DURÉES MULTIPLES =====
        personnaliser = st.checkbox("🔧 Personnaliser les phases")
        phases_personnalisees = []
        
        if personnaliser:
            st.write("**Phases personnalisées :**")
            nb_phases = st.number_input("Nombre de phases", min_value=1, max_value=100, value=5)  # LIMITE SUPPRIMÉE
            
            for i in range(nb_phases):
                with st.container():
                    col_nom, col_duree, col_unite, col_couleur = st.columns([3, 1, 1, 1])
                    with col_nom:
                        phase_nom = st.text_input(f"Phase {i+1}", key=f"phase_nom_{i}")
                    with col_duree:
                        phase_duree = st.number_input(f"Durée", min_value=1, value=30, key=f"phase_duree_{i}")
                    with col_unite:
                        phase_unite = st.selectbox("Unité", ["jours", "semaines", "mois"], key=f"phase_unite_{i}")
                    with col_couleur:
                        phase_couleur = st.color_picker("Couleur", "#1f77b4", key=f"phase_couleur_{i}")
                    
                    if phase_nom:
                        duree_jours = convert_to_days(phase_duree, phase_unite)
                        phases_personnalisees.append({
                            "nom": phase_nom,
                            "duree_jours": duree_jours,
                            "couleur": phase_couleur
                        })
        
        submitted = st.form_submit_button("🚀 Créer l'Opération", type="primary")
        
        if submitted:
            # Validation
            if not nom or not type_operation or not aco_responsable:
                st.error("Veuillez remplir tous les champs obligatoires (*)")
                return
            
            if date_debut >= date_fin:
                st.error("La date de fin doit être postérieure à la date de début")
                return
            
            # Créer l'opération
            operation_id = str(uuid.uuid4())
            
            # Utiliser les phases personnalisées ou le template
            phases_template = phases_personnalisees if personnaliser and phases_personnalisees else TEMPLATES_PHASES[type_operation]
            
            # Créer les phases
            phases = []
            current_date = datetime.combine(date_debut, datetime.min.time())
            
            for phase_template in phases_template:
                phase_id = str(uuid.uuid4())
                date_fin_phase = current_date + timedelta(days=phase_template["duree_jours"] - 1)
                
                phase = Phase(
                    id=phase_id,
                    nom=phase_template["nom"],
                    date_debut=current_date,
                    date_fin=date_fin_phase,
                    couleur=phase_template["couleur"],
                    statut="En attente",
                    responsable=aco_responsable
                )
                phases.append(phase)
                current_date = date_fin_phase + timedelta(days=1)
            
            # Créer l'opération
            operation = Operation(
                id=operation_id,
                nom=nom,
                type_operation=type_operation,
                aco_responsable=aco_responsable,
                date_creation=datetime.now(),
                date_debut=datetime.combine(date_debut, datetime.min.time()),
                date_fin_prevue=datetime.combine(date_fin, datetime.min.time()),
                budget=budget,
                statut="Créée",
                phases=phases
            )
            
            # Sauvegarder
            db.save_operation(operation)
            
            # Mettre à jour sélection
            st.session_state.selected_operation_id = operation_id
            
            st.success(f"✅ Opération '{nom}' créée avec succès avec {len(phases)} phases !")
            st.balloons()
            
            # Afficher un aperçu de la timeline
            st.subheader("📊 Aperçu de la Timeline")
            fig = create_timeline_gantt(operation)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            # SYNCHRONISATION FORCÉE
            st.rerun()

def operations_en_cours():
    """Module des opérations en cours (ancien Timeline Gantt) - SYNCHRONISÉ"""
    st.header("📊 Opérations en cours")  # NAVIGATION COHÉRENTE
    
    db = get_database()
    operations = db.load_operations()
    
    if not operations:
        st.warning("Aucune opération trouvée. Créez d'abord une opération.")
        return
    
    # Sélection de l'opération avec pré-sélection
    operation_names = [f"{op.nom} ({op.type_operation})" for op in operations]
    
    # Trouver l'index de l'opération pré-sélectionnée
    default_index = 0
    if st.session_state.selected_operation_id:
        for i, op in enumerate(operations):
            if op.id == st.session_state.selected_operation_id:
                default_index = i
                break
    
    selected_name = st.selectbox(
        "Sélectionner une opération", 
        operation_names, 
        index=default_index,
        key="operation_selector"
    )
    
    if selected_name:
        # Trouver l'opération sélectionnée
        selected_operation = None
        for op in operations:
            if f"{op.nom} ({op.type_operation})" == selected_name:
                selected_operation = op
                st.session_state.selected_operation_id = op.id
                break
        
        if selected_operation:
            # Informations de l'opération
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Type", selected_operation.type_operation)
            with col2:
                st.metric("ACO", selected_operation.aco_responsable)
            with col3:
                st.metric("Budget", f"{selected_operation.budget:,.0f} €")
            with col4:
                phases_completed = len([p for p in selected_operation.phases if p.statut == "Terminé"])
                progress_pct = (phases_completed / len(selected_operation.phases) * 100) if selected_operation.phases else 0
                st.metric("Avancement", f"{progress_pct:.1f}%", f"{phases_completed}/{len(selected_operation.phases)} phases")
            
            # Timeline Gantt synchronisée
            st.subheader("🎯 Timeline Interactive")
            fig = create_timeline_gantt(selected_operation)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            # Gestion des phases
            st.subheader("⚙️ Gestion des Phases")
            
            tabs = st.tabs(["📋 Liste des Phases", "➕ Ajouter Phase", "🔧 Modifier Phase"])
            
            with tabs[0]:
                # Liste des phases avec actions rapides
                for i, phase in enumerate(selected_operation.phases):
                    with st.expander(f"{i+1}. {phase.nom} ({phase.statut})", expanded=phase.statut == "Retard" or phase.freins):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Début :** {phase.date_debut.strftime('%d/%m/%Y')}")
                            st.write(f"**Fin :** {phase.date_fin.strftime('%d/%m/%Y')}")
                            duration_days = (phase.date_fin - phase.date_debut).days + 1
                            st.write(f"**Durée :** {format_duration(duration_days)}")
                        with col2:
                            st.write(f"**Statut :** {phase.statut}")
                            st.write(f"**Responsable :** {phase.responsable}")
                            if phase.freins:
                                st.error(f"**Freins ({len(phase.freins)}) :** {', '.join(phase.freins)}")
                        
                        if phase.description:
                            st.write(f"**Description :** {phase.description}")
                        
                        # Actions rapides avec SYNCHRONISATION
                        col_act1, col_act2, col_act3 = st.columns(3)
                        with col_act1:
                            if st.button(f"✅ Terminer", key=f"complete_{phase.id}"):
                                phase.statut = "Terminé"
                                db.save_operation(selected_operation)
                                st.success("Phase marquée comme terminée !")
                                st.rerun()  # SYNCHRONISATION
                        with col_act2:
                            if st.button(f"🚀 Démarrer", key=f"start_{phase.id}"):
                                phase.statut = "En cours"
                                db.save_operation(selected_operation)
                                st.success("Phase marquée en cours !")
                                st.rerun()  # SYNCHRONISATION
                        with col_act3:
                            if st.button(f"⚠️ Retard", key=f"delay_{phase.id}"):
                                phase.statut = "Retard"
                                db.save_operation(selected_operation)
                                st.warning("Phase marquée en retard !")
                                st.rerun()  # SYNCHRONISATION
            
            with tabs[1]:
                # Ajouter une nouvelle phase avec DURÉES MULTIPLES
                st.write("Ajouter une nouvelle phase à l'opération")
                
                with st.form("add_phase"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_phase_nom = st.text_input("Nom de la phase")
                        new_duree = st.number_input("Durée", min_value=1, value=30)
                        new_unite = st.selectbox("Unité", ["jours", "semaines", "mois"])
                    with col2:
                        new_phase_responsable = st.text_input("Responsable", value=selected_operation.aco_responsable)
                        new_phase_couleur = st.color_picker("Couleur", "#1f77b4")
                    
                    new_phase_description = st.text_area("Description (optionnel)")
                    
                    # Position d'insertion
                    positions = ["À la fin"] + [f"Avant '{phase.nom}'" for phase in selected_operation.phases]
                    position = st.selectbox("Insérer", positions)
                    
                    if st.form_submit_button("Ajouter la Phase"):
                        if new_phase_nom:
                            # Convertir la durée en jours
                            new_phase_duree = convert_to_days(new_duree, new_unite)
                            
                            # Calculer les dates
                            if position == "À la fin" and selected_operation.phases:
                                date_debut = selected_operation.phases[-1].date_fin + timedelta(days=1)
                            elif position != "À la fin":
                                # Trouver la position d'insertion
                                idx = positions.index(position) - 1
                                date_debut = selected_operation.phases[idx].date_debut
                                # Décaler les phases suivantes
                                for phase in selected_operation.phases[idx:]:
                                    phase.date_debut += timedelta(days=new_phase_duree)
                                    phase.date_fin += timedelta(days=new_phase_duree)
                            else:
                                date_debut = selected_operation.date_debut
                            
                            date_fin = date_debut + timedelta(days=new_phase_duree - 1)
                            
                            # Créer la nouvelle phase
                            new_phase = Phase(
                                id=str(uuid.uuid4()),
                                nom=new_phase_nom,
                                date_debut=date_debut,
                                date_fin=date_fin,
                                couleur=new_phase_couleur,
                                statut="En attente",
                                description=new_phase_description,
                                responsable=new_phase_responsable
                            )
                            
                            # Insérer dans la liste
                            if position == "À la fin":
                                selected_operation.phases.append(new_phase)
                            else:
                                idx = positions.index(position) - 1
                                selected_operation.phases.insert(idx, new_phase)
                            
                            # Sauvegarder avec SYNCHRONISATION
                            db.save_operation(selected_operation)
                            st.success("Phase ajoutée avec succès !")
                            st.rerun()  # SYNCHRONISATION TIMELINE
            
            with tabs[2]:
                # Modifier une phase existante avec VALIDATION FONCTIONNELLE
                if selected_operation.phases:
                    phase_names = [f"{phase.nom} ({phase.statut})" for phase in selected_operation.phases]
                    selected_phase_name = st.selectbox("Sélectionner une phase à modifier", phase_names)
                    
                    if selected_phase_name:
                        # Trouver la phase sélectionnée
                        selected_phase = None
                        for phase in selected_operation.phases:
                            if f"{phase.nom} ({phase.statut})" == selected_phase_name:
                                selected_phase = phase
                                break
                        
                        if selected_phase:
                            with st.form("modify_phase"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    mod_statut = st.selectbox("Statut", 
                                        ["En attente", "En cours", "Terminé", "Retard"],
                                        index=["En attente", "En cours", "Terminé", "Retard"].index(selected_phase.statut)
                                    )
                                    mod_responsable = st.text_input("Responsable", value=selected_phase.responsable)
                                with col2:
                                    mod_date_debut = st.date_input("Date début", value=selected_phase.date_debut.date())
                                    mod_date_fin = st.date_input("Date fin", value=selected_phase.date_fin.date())
                                
                                mod_description = st.text_area("Description", value=selected_phase.description)
                                
                                # ===== GESTION FREINS OPÉRATIONNELLE =====
                                st.write("**Freins identifiés :**")
                                freins_actuels = selected_phase.freins.copy()
                                
                                # Afficher les freins existants
                                if freins_actuels:
                                    for frein in freins_actuels:
                                        st.error(f"• {frein}")
                                
                                # Ajouter nouveau frein
                                nouveau_frein = st.text_input("Ajouter un frein")
                                
                                # Freins prédéfinis
                                freins_predefinies = [
                                    "Retard fournisseur",
                                    "Problème technique",
                                    "Attente validation",
                                    "Conditions météo",
                                    "Problème administratif",
                                    "Manque de ressources",
                                    "Dépendance externe"
                                ]
                                frein_predefini = st.selectbox("Ou sélectionner un frein prédéfini", [""] + freins_predefinies)
                                
                                # Actions freins
                                col_clear, col_add = st.columns(2)
                                with col_clear:
                                    clear_freins = st.checkbox("Lever tous les freins")
                                with col_add:
                                    add_frein = nouveau_frein or frein_predefini
                                
                                if st.form_submit_button("💾 Modifier la Phase"):
                                    # Mettre à jour la phase
                                    selected_phase.statut = mod_statut
                                    selected_phase.responsable = mod_responsable
                                    selected_phase.date_debut = datetime.combine(mod_date_debut, datetime.min.time())
                                    selected_phase.date_fin = datetime.combine(mod_date_fin, datetime.min.time())
                                    selected_phase.description = mod_description
                                    
                                    # Gestion des freins
                                    if clear_freins:
                                        selected_phase.freins = []
                                    if add_frein and add_frein not in selected_phase.freins:
                                        selected_phase.freins.append(add_frein)
                                    
                                    # Sauvegarder avec SYNCHRONISATION
                                    db.save_operation(selected_operation)
                                    st.success("Phase modifiée avec succès !")
                                    st.rerun()  # SYNCHRONISATION TIMELINE

# ===== MODULES ACTIFS (VERT) =====
def gestion_aco():
    """Module de gestion des ACO - MAINTENANT ACTIF"""
    st.header("👥 Gestion ACO")
    
    db = get_database()
    aco_list = db.load_aco()
    operations = db.load_operations()
    
    tabs = st.tabs(["📋 Liste des ACO", "📊 Performances", "👤 Détail ACO"])
    
    with tabs[0]:
        # Liste des ACO avec leurs statistiques
        st.subheader("📋 Équipe ACO SPIC Guadeloupe")
        
        for aco in aco_list:
            with st.container():
                st.markdown(f"""
                <div class="aco-card">
                    <h4>👤 {aco.nom}</h4>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Opérations en cours", aco.operations_en_cours)
                with col2:
                    st.metric("Budget total", f"{aco.total_budget:,.0f} €")
                with col3:
                    st.write(f"**Email :** {aco.email}")
                with col4:
                    st.write(f"**Téléphone :** {aco.telephone}")
                
                # Spécialités
                specialites_str = " | ".join(aco.specialites)
                st.write(f"**Spécialités :** {specialites_str}")
                
                # LIAISON ACO ↔ OPÉRATIONS OPÉRATIONNELLE
                if st.button(f"Voir les opérations de {aco.nom}", key=f"voir_{aco.nom}"):
                    st.session_state.selected_aco = aco.nom
                    st.rerun()
                
                st.markdown("---")
    
    with tabs[1]:
        # Performances des ACO
        st.subheader("📊 Tableau de Bord des Performances")
        
        if aco_list:
            # Graphique des opérations par ACO
            aco_names = [aco.nom for aco in aco_list]
            operations_counts = [aco.operations_en_cours for aco in aco_list]
            budgets = [aco.total_budget for aco in aco_list]
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_ops = px.bar(
                    x=aco_names, 
                    y=operations_counts,
                    title="Opérations en cours par ACO",
                    labels={'x': 'ACO', 'y': 'Nombre d\'opérations'},
                    color=operations_counts,
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_ops, use_container_width=True)
            
            with col2:
                fig_budget = px.bar(
                    x=aco_names, 
                    y=budgets,
                    title="Budget total géré par ACO",
                    labels={'x': 'ACO', 'y': 'Budget (€)'},
                    color=budgets,
                    color_continuous_scale='Greens'
                )
                st.plotly_chart(fig_budget, use_container_width=True)
            
            # Statistiques détaillées
            st.subheader("📈 Analyse des Performances")
            
            for aco in aco_list:
                aco_operations = [op for op in operations if op.aco_responsable == aco.nom]
                
                if aco_operations:
                    # Calculer les métriques
                    phases_retard = sum(1 for op in aco_operations for phase in op.phases if phase.statut == "Retard")
                    phases_freins = sum(1 for op in aco_operations for phase in op.phases if phase.freins)
                    budget_moyen = aco.total_budget / len(aco_operations) if aco_operations else 0
                    
                    with st.expander(f"📊 Détail {aco.nom}"):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Opérations totales", len(aco_operations))
                        with col2:
                            st.metric("Phases en retard", phases_retard)
                        with col3:
                            st.metric("Phases avec freins", phases_freins)
                        with col4:
                            st.metric("Budget moyen", f"{budget_moyen:,.0f} €")
    
    with tabs[2]:
        # Détail ACO sélectionné avec WORKFLOW
        if st.session_state.selected_aco:
            selected_aco_obj = None
            for aco in aco_list:
                if aco.nom == st.session_state.selected_aco:
                    selected_aco_obj = aco
                    break
            
            if selected_aco_obj:
                st.subheader(f"👤 Détail {selected_aco_obj.nom}")
                
                # Informations personnelles
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Email :** {selected_aco_obj.email}")
                    st.write(f"**Téléphone :** {selected_aco_obj.telephone}")
                with col2:
                    st.write(f"**Spécialités :** {' | '.join(selected_aco_obj.specialites)}")
                
                # Opérations de cet ACO
                aco_operations = [op for op in operations if op.aco_responsable == selected_aco_obj.nom]
                
                if aco_operations:
                    st.subheader(f"📋 Opérations de {selected_aco_obj.nom} ({len(aco_operations)})")
                    
                    # Tableau des opérations avec NAVIGATION
                    data = []
                    for op in aco_operations:
                        phases_completed = len([p for p in op.phases if p.statut == "Terminé"])
                        phases_retard = len([p for p in op.phases if p.statut == "Retard"])
                        phases_freins = sum(1 for p in op.phases if p.freins)
                        
                        status_indicator = "🟢"
                        if phases_retard > 0:
                            status_indicator = "🔴"
                        elif phases_freins > 0:
                            status_indicator = "🟠"
                        
                        data.append({
                            "🎯": status_indicator,
                            "Nom": op.nom,
                            "Type": op.type_operation,
                            "Statut": op.statut,
                            "Budget": f"{op.budget:,.0f} €",
                            "Progression": f"{phases_completed}/{len(op.phases)}",
                            "Retards": phases_retard,
                            "Freins": phases_freins,
                            "Créée": op.date_creation.strftime("%d/%m/%Y")
                        })
                    
                    df = pd.DataFrame(data)
                    
                    # Sélection d'opération avec navigation
                    event = st.dataframe(
                        df, 
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode="single-row"
                    )
                    
                    # Navigation vers l'opération sélectionnée
                    if event.selection and event.selection.rows:
                        selected_idx = event.selection.rows[0]
                        selected_op = aco_operations[selected_idx]
                        st.session_state.selected_operation_id = selected_op.id
                        st.success(f"✅ Opération '{selected_op.nom}' sélectionnée. Allez dans 'Opérations en cours' pour voir les détails.")
                else:
                    st.info(f"Aucune opération assignée à {selected_aco_obj.nom}")
        else:
            st.info("Sélectionnez un ACO dans l'onglet 'Liste des ACO' pour voir les détails.")

def freins_alertes():
    """Module de gestion des freins et alertes - MAINTENANT ACTIF"""
    st.header("🚨 Freins & Alertes")
    
    db = get_database()
    operations = db.load_operations()
    
    # Collecter toutes les alertes
    alertes_retard = []
    alertes_freins = []
    
    for op in operations:
        for phase in op.phases:
            if phase.statut == "Retard":
                alertes_retard.append({
                    "operation": op,
                    "phase": phase,
                    "gravite": "Critique"
                })
            if phase.freins:
                alertes_freins.append({
                    "operation": op,
                    "phase": phase,
                    "freins": phase.freins,
                    "gravite": "Élevée" if len(phase.freins) > 2 else "Modérée"
                })
    
    # Métriques d'alerte
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔴 Phases en Retard", len(alertes_retard))
    with col2:
        st.metric("🟠 Phases avec Freins", len(alertes_freins))
    with col3:
        total_freins = sum(len(alert["freins"]) for alert in alertes_freins)
        st.metric("📊 Total Freins", total_freins)
    with col4:
        alertes_critiques = len([a for a in alertes_retard]) + len([a for a in alertes_freins if a["gravite"] == "Élevée"])
        st.metric("⚠️ Alertes Critiques", alertes_critiques)
    
    tabs = st.tabs(["🔴 Retards", "🟠 Freins", "📊 Tableau de Bord"])
    
    with tabs[0]:
        # Gestion des retards
        st.subheader("🔴 Phases en Retard")
        
        if alertes_retard:
            for i, alerte in enumerate(alertes_retard):
                op = alerte["operation"]
                phase = alerte["phase"]
                
                st.markdown(f"""
                <div class="frein-critical">
                    <h5>⚠️ {op.nom} - {phase.nom}</h5>
                    <p><strong>ACO:</strong> {op.aco_responsable} | <strong>Type:</strong> {op.type_operation}</p>
                    <p><strong>Période:</strong> {phase.date_debut.strftime('%d/%m/%Y')} → {phase.date_fin.strftime('%d/%m/%Y')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button(f"✅ Résolu", key=f"resolve_retard_{i}"):
                        phase.statut = "En cours"
                        db.save_operation(op)
                        st.success("Retard résolu !")
                        st.rerun()
                with col2:
                    if st.button(f"📅 Reprogrammer", key=f"reschedule_{i}"):
                        # Ajouter 7 jours à la date de fin
                        phase.date_fin += timedelta(days=7)
                        db.save_operation(op)
                        st.info("Phase reprogrammée (+7 jours)")
                        st.rerun()
                with col3:
                    if st.button(f"👁️ Voir Détail", key=f"view_retard_{i}"):
                        st.session_state.selected_operation_id = op.id
                        st.info("Allez dans 'Opérations en cours' pour plus de détails.")
        else:
            st.success("✅ Aucune phase en retard !")
    
    with tabs[1]:
        # Gestion des freins
        st.subheader("🟠 Freins Identifiés")
        
        if alertes_freins:
            for i, alerte in enumerate(alertes_freins):
                op = alerte["operation"]
                phase = alerte["phase"]
                freins = alerte["freins"]
                
                st.markdown(f"""
                <div class="frein-alert">
                    <h5>🛑 {op.nom} - {phase.nom}</h5>
                    <p><strong>ACO:</strong> {op.aco_responsable} | <strong>Gravité:</strong> {alerte['gravite']}</p>
                    <p><strong>Freins ({len(freins)}):</strong> {', '.join(freins)}</p>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button(f"✅ Lever Freins", key=f"resolve_frein_{i}"):
                        phase.freins = []
                        db.save_operation(op)
                        st.success("Freins levés !")
                        st.rerun()
                with col2:
                    # Ajouter frein avec formulaire rapide
                    with st.form(f"add_frein_form_{i}"):
                        new_frein = st.text_input("Nouveau frein", key=f"new_frein_{i}")
                        if st.form_submit_button("➕"):
                            if new_frein:
                                phase.freins.append(new_frein)
                                db.save_operation(op)
                                st.success("Frein ajouté !")
                                st.rerun()
                with col3:
                    if st.button(f"👁️ Voir Détail", key=f"view_frein_{i}"):
                        st.session_state.selected_operation_id = op.id
                        st.info("Allez dans 'Opérations en cours' pour plus de détails.")
        else:
            st.success("✅ Aucun frein identifié !")
    
    with tabs[2]:
        # Tableau de bord des alertes
        st.subheader("📊 Tableau de Bord des Alertes")
        
        # Graphique des alertes par ACO
        aco_alerts = {}
        for op in operations:
            aco = op.aco_responsable
            if aco not in aco_alerts:
                aco_alerts[aco] = {"retards": 0, "freins": 0}
            
            for phase in op.phases:
                if phase.statut == "Retard":
                    aco_alerts[aco]["retards"] += 1
                if phase.freins:
                    aco_alerts[aco]["freins"] += len(phase.freins)
        
        if aco_alerts:
            df_alerts = pd.DataFrame.from_dict(aco_alerts, orient='index')
            df_alerts['ACO'] = df_alerts.index
            df_alerts['Total_Alertes'] = df_alerts['retards'] + df_alerts['freins']
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_retards = px.bar(
                    df_alerts, 
                    x='ACO', 
                    y='retards',
                    title="Retards par ACO",
                    color='retards',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig_retards, use_container_width=True)
            
            with col2:
                fig_freins = px.bar(
                    df_alerts, 
                    x='ACO', 
                    y='freins',
                    title="Freins par ACO",
                    color='freins',
                    color_continuous_scale='Oranges'
                )
                st.plotly_chart(fig_freins, use_container_width=True)

def main():
    """Fonction principale avec navigation cohérente"""
    
    # Sidebar avec navigation
    st.sidebar.markdown("""
        <div class="sidebar-logo">
            <h2>🏗️ OPCOPILOT</h2>
            <p>SPIC Guadeloupe v3.0</p>
        </div>
    """, unsafe_allow_html=True)
    
    # ===== NAVIGATION COHÉRENTE =====
    pages = {
        "🏠 Dashboard": dashboard,
        "➕ Nouvelle Opération": nouvelle_operation,
        "📊 Opérations en cours": operations_en_cours,  # NAVIGATION COHÉRENTE
        "👥 Gestion ACO": gestion_aco,  # MAINTENANT ACTIF (VERT)
        "🚨 Freins & Alertes": freins_alertes  # MAINTENANT ACTIF (VERT)
    }
    
    selected_page = st.sidebar.selectbox("Navigation", list(pages.keys()))
    
    # ===== MODULES DISPONIBLES (CORRECTION STATUTS) =====
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Modules Disponibles")
    modules = [
        "✅ Dashboard KPIs",
        "✅ Création Opération", 
        "✅ Opérations en cours",  # NAVIGATION COHÉRENTE
        "✅ Gestion ACO",  # MAINTENANT VERT (ACTIF)
        "✅ Freins & Alertes",  # MAINTENANT VERT (ACTIF)
        "🔄 REM Saisie (v3.1)",
        "🔄 Avenants (v3.1)",
        "🔄 MED Automatisé (v3.1)",
        "🔄 Concessionnaires (v3.1)",
        "🔄 DGD (v3.1)",
        "🔄 GPA (v3.1)",
        "🔄 Levée Réserves (v3.1)"
    ]
    
    for module in modules:
        if module.startswith("✅"):
            st.sidebar.success(module)
        else:
            st.sidebar.info(module)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 Version Actuelle")
    st.sidebar.info("OPCOPILOT v3.0 CORRIGÉ\n✅ Templates métier exacts\n✅ 5 Modules actifs\n✅ Timeline synchronisée\nJuin 2025")
    
    # Session state pour la navigation
    if st.session_state.selected_operation_id:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎯 Opération Sélectionnée")
        db = get_database()
        operations = db.load_operations()
        selected_op = None
        for op in operations:
            if op.id == st.session_state.selected_operation_id:
                selected_op = op
                break
        
        if selected_op:
            st.sidebar.info(f"📋 {selected_op.nom}\n👤 {selected_op.aco_responsable}")
            if st.sidebar.button("🗑️ Désélectionner"):
                st.session_state.selected_operation_id = None
                st.rerun()
    
    # Exécuter la page sélectionnée
    pages[selected_page]()

if __name__ == "__main__":
    main()
