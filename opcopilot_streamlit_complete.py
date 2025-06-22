# 🏗️ OPCOPILOT STREAMLIT - APPLICATION COMPLÈTE
# Transformation finale Reflex → Streamlit pour SPIC Guadeloupe

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid

# Configuration page Streamlit
st.set_page_config(
    page_title="OPCOPILOT - Outil Central MOA",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "OPCOPILOT v2.0 - SPIC Guadeloupe - Outil Central de Maîtrise d'Ouvrage"
    }
)

# ============================================================================
# MODÈLES DE DONNÉES STREAMLIT
# ============================================================================

@dataclass
class Operation:
    """Modèle d'opération pour Streamlit"""
    id: int
    numero: str
    nom: str
    type_operation: str  # OPP/VEFA/MANDAT/AMO
    commune: str
    statut_global: str
    avancement_pct: float
    aco_responsable: str
    budget_initial: float
    rem_projetee: float
    rem_generee: float
    nb_logements_lls: int = 0
    nb_logements_llts: int = 0
    nb_logements_pls: int = 0
    date_creation: str = ""
    date_livraison_prevue: str = ""
    est_active: bool = True
    nb_freins_actifs: int = 0
    score_risque: float = 0.0

@dataclass
class Phase:
    """Modèle de phase pour Streamlit"""
    id: int
    operation_id: int
    ordre: int
    nom: str
    description: str
    domaine: str  # OPERATIONNEL/JURIDIQUE/BUDGETAIRE/ADMINISTRATIF
    statut: str  # EN_ATTENTE/EN_COURS/VALIDE/BLOQUE/FREIN
    est_validee: bool
    est_critique: bool
    date_debut_prevue: str
    date_fin_prevue: str
    date_validation: str = ""
    responsable_principal: str = ""
    duree_mini_jours: int = 1
    duree_maxi_jours: int = 30
    impact_rem: bool = False

@dataclass
class Frein:
    """Modèle de frein pour Streamlit"""
    id: int
    phase_id: int
    operation_id: int
    titre: str
    description: str
    type_frein: str
    statut_frein: str
    niveau_impact: str
    date_signalement: str
    signale_par: str
    actions_correctives: str = ""
    date_resolution: str = ""

# ============================================================================
# WORKFLOW OPP COMPLET - 45 PHASES
# ============================================================================

class OPPWorkflow:
    """Workflow OPP adapté pour Streamlit - 45 phases chronologiques"""
    
    PHASES_OPP = [
        # PHASE 1 : MONTAGE OPÉRATION (4 phases)
        {"ordre": 1, "nom": "Opportunité foncière identifiée", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 21},
        {"ordre": 2, "nom": "Étude de faisabilité technique", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 30},
        {"ordre": 3, "nom": "Programmation détaillée validée", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 40},
        {"ordre": 4, "nom": "Acquisition/réservation foncière", "domaine": "JURIDIQUE", "critique": True, "duree_moy": 105},
        
        # PHASE 2 : ÉTUDES DE CONCEPTION (6 phases)
        {"ordre": 5, "nom": "Consultation architecte", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 33},
        {"ordre": 6, "nom": "Esquisse (ESQ)", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 31},
        {"ordre": 7, "nom": "Avant-Projet Sommaire (APS)", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 42},
        {"ordre": 8, "nom": "Avant-Projet Détaillé (APD)", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 63},
        {"ordre": 9, "nom": "Projet (PRO)", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 84},
        {"ordre": 10, "nom": "Dossier de Consultation Entreprises (DCE)", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 42},
        
        # PHASE 3 : AUTORISATIONS ADMINISTRATIVES (4 phases)
        {"ordre": 11, "nom": "Constitution dossier Permis de Construire", "domaine": "ADMINISTRATIF", "critique": False, "duree_moy": 21},
        {"ordre": 12, "nom": "Dépôt Permis de Construire", "domaine": "ADMINISTRATIF", "critique": False, "duree_moy": 4},
        {"ordre": 13, "nom": "Instruction Permis de Construire", "domaine": "ADMINISTRATIF", "critique": True, "duree_moy": 135},
        {"ordre": 14, "nom": "Purge délai de recours", "domaine": "ADMINISTRATIF", "critique": True, "duree_moy": 75},
        
        # PHASE 4 : MONTAGE FINANCIER (6 phases)
        {"ordre": 15, "nom": "Constitution Ligne Budget Utilisateur (LBU)", "domaine": "BUDGETAIRE", "critique": False, "duree_moy": 45},
        {"ordre": 16, "nom": "Vote LBU en Conseil d'Administration", "domaine": "BUDGETAIRE", "critique": True, "duree_moy": 18},
        {"ordre": 17, "nom": "Dossier financement Caisse des Dépôts", "domaine": "BUDGETAIRE", "critique": False, "duree_moy": 67},
        {"ordre": 18, "nom": "Signature contrat de prêt CDC", "domaine": "BUDGETAIRE", "critique": False, "duree_moy": 29},
        {"ordre": 19, "nom": "Recherche cofinancements", "domaine": "BUDGETAIRE", "critique": False, "duree_moy": 75},
        {"ordre": 20, "nom": "Constitution garanties et sûretés", "domaine": "BUDGETAIRE", "critique": False, "duree_moy": 40},
        
        # PHASE 5 : CONSULTATION ENTREPRISES (5 phases)
        {"ordre": 21, "nom": "Lancement consultation travaux", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 6},
        {"ordre": 22, "nom": "Période de consultation", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 41},
        {"ordre": 23, "nom": "Ouverture et analyse des offres", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 24},
        {"ordre": 24, "nom": "Négociation (si procédure le permet)", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 14},
        {"ordre": 25, "nom": "Commission d'Appel d'Offres (CAO)", "domaine": "JURIDIQUE", "critique": True, "duree_moy": 7},
        
        # PHASE 6 : ATTRIBUTION ET PASSATION (4 phases)
        {"ordre": 26, "nom": "Notification marché au(x) attributaire(s)", "domaine": "JURIDIQUE", "critique": False, "duree_moy": 6},
        {"ordre": 27, "nom": "Constitution dossier marché", "domaine": "JURIDIQUE", "critique": False, "duree_moy": 28},
        {"ordre": 28, "nom": "Signature marché de travaux", "domaine": "JURIDIQUE", "critique": True, "duree_moy": 14},
        {"ordre": 29, "nom": "Ordre de Service de démarrage", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 18},
        
        # PHASE 7 : EXÉCUTION TRAVAUX (7 phases)
        {"ordre": 30, "nom": "Date d'Ouverture de Chantier (DOC)", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 4, "rem": True},
        {"ordre": 31, "nom": "Travaux de fondations", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 60, "rem": True},
        {"ordre": 32, "nom": "Élévation - Hors d'eau", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 105, "rem": True},
        {"ordre": 33, "nom": "Second œuvre - Hors d'air", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 135, "rem": True},
        {"ordre": 34, "nom": "Finitions et équipements", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 90, "rem": True},
        {"ordre": 35, "nom": "Réunions de chantier (tout au long)", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 10},
        {"ordre": 36, "nom": "Date d'Achèvement des Travaux (DACT)", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 2, "rem": True},
        
        # PHASE 8 : RÉCEPTION ET LIVRAISON (5 phases)
        {"ordre": 37, "nom": "Opérations Préalables à la Réception (OPR)", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 14},
        {"ordre": 38, "nom": "Pré-réception SPIC", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 10},
        {"ordre": 39, "nom": "Réception définitive", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 4, "rem": True},
        {"ordre": 40, "nom": "Remise Dossier des Ouvrages Exécutés (DOE)", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 45},
        {"ordre": 41, "nom": "Remise DIUO", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 33},
        
        # PHASE 9 : MISE EN GESTION (3 phases)
        {"ordre": 42, "nom": "Livraison aux locataires", "domaine": "OPERATIONNEL", "critique": True, "duree_moy": 29, "rem": True},
        {"ordre": 43, "nom": "Mise en gestion locative", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 18},
        {"ordre": 44, "nom": "Bilan de commercialisation", "domaine": "OPERATIONNEL", "critique": False, "duree_moy": 22},
        
        # PHASE 10 : CLÔTURE OPÉRATION (1 phase)
        {"ordre": 45, "nom": "Clôture administrative", "domaine": "ADMINISTRATIF", "critique": True, "duree_moy": 60, "rem": True}
    ]
    
    @classmethod
    def generer_phases_demo(cls, operation_id: int, avancement_pct: float) -> List[Phase]:
        """Génère les phases pour une opération selon son avancement"""
        phases = []
        nb_phases_validees = int(len(cls.PHASES_OPP) * avancement_pct / 100)
        
        for i, phase_data in enumerate(cls.PHASES_OPP):
            statut = "VALIDE" if i < nb_phases_validees else "EN_ATTENTE"
            if i == nb_phases_validees and avancement_pct < 100:
                statut = "EN_COURS"
            
            # Frein sur Nérée Servant (operation 8045) à la phase LBU
            if operation_id == 8045 and phase_data["ordre"] == 15:
                statut = "FREIN"
            
            phase = Phase(
                id=operation_id * 1000 + phase_data["ordre"],
                operation_id=operation_id,
                ordre=phase_data["ordre"],
                nom=phase_data["nom"],
                description=f"Phase {phase_data['ordre']} du workflow OPP",
                domaine=phase_data["domaine"],
                statut=statut,
                est_validee=(statut == "VALIDE"),
                est_critique=phase_data["critique"],
                date_debut_prevue=(datetime.now() + timedelta(days=i*7)).strftime("%Y-%m-%d"),
                date_fin_prevue=(datetime.now() + timedelta(days=i*7 + phase_data["duree_moy"])).strftime("%Y-%m-%d"),
                responsable_principal="ACO" if i % 3 == 0 else "MOE",
                duree_mini_jours=phase_data["duree_moy"] // 2,
                duree_maxi_jours=phase_data["duree_moy"] * 2,
                impact_rem=phase_data.get("rem", False)
            )
            phases.append(phase)
        
        return phases

# ============================================================================
# GESTIONNAIRE DE DONNÉES GLOBAL
# ============================================================================

class DataManager:
    """Gestionnaire centralisé des données OPCOPILOT"""
    
    def __init__(self):
        self.init_session_state()
        self.load_operations_data()
        self.load_phases_data()
        self.load_freins_data()
    
    def init_session_state(self):
        """Initialise le state Streamlit"""
        if 'initialized' not in st.session_state:
            st.session_state.initialized = True
            st.session_state.user_nom = "Marie-Claire ADMIN"
            st.session_state.user_role = "ACO"
            st.session_state.operations = []
            st.session_state.phases = {}  # par operation_id
            st.session_state.freins = []
            st.session_state.current_operation_id = None
            st.session_state.portfolio_stats = {}
            st.session_state.meds_actives = []
            st.session_state.os_operations = {}
            st.session_state.dgd_operations = {}
    
    def load_operations_data(self):
        """Charge les données des opérations"""
        if not st.session_state.operations:
            st.session_state.operations = [
                Operation(
                    id=8021,
                    numero="8021",
                    nom="Cour Charneau",
                    type_operation="OPP",
                    commune="Les Abymes",
                    statut_global="TRAVAUX",
                    avancement_pct=65.0,
                    aco_responsable="MCA",
                    budget_initial=3200000,
                    rem_projetee=112000,
                    rem_generee=72800,
                    nb_logements_lls=32,
                    nb_logements_llts=12,
                    date_creation="2019-01-31",
                    date_livraison_prevue="2026-02-01",
                    nb_freins_actifs=1,
                    score_risque=45.2
                ),
                Operation(
                    id=8028,
                    numero="8028",
                    nom="Zonis ZB1 Tr2",
                    type_operation="OPP",
                    commune="Les Abymes",
                    statut_global="APPEL_OFFRES",
                    avancement_pct=35.0,
                    aco_responsable="MCA",
                    budget_initial=2800000,
                    rem_projetee=98000,
                    rem_generee=34300,
                    nb_logements_lls=28,
                    nb_logements_llts=10,
                    date_creation="2017-10-17",
                    date_livraison_prevue="2026-02-01",
                    nb_freins_actifs=0,
                    score_risque=22.1
                ),
                Operation(
                    id=8042,
                    numero="8042",
                    nom="St Jean",
                    type_operation="VEFA",
                    commune="Petit-Bourg",
                    statut_global="LIVREE",
                    avancement_pct=95.0,
                    aco_responsable="LU",
                    budget_initial=5200000,
                    rem_projetee=130000,
                    rem_generee=123500,
                    nb_logements_lls=60,
                    nb_logements_llts=20,
                    date_creation="2018-07-25",
                    date_livraison_prevue="2023-12-01",
                    nb_freins_actifs=0,
                    score_risque=8.5
                ),
                Operation(
                    id=8044,
                    numero="8044",
                    nom="Effervescence",
                    type_operation="OPP",
                    commune="Saint-François",
                    statut_global="TRAVAUX",
                    avancement_pct=72.0,
                    aco_responsable="ROS",
                    budget_initial=2100000,
                    rem_projetee=73500,
                    rem_generee=52920,
                    nb_logements_lls=19,
                    nb_logements_llts=8,
                    date_creation="2019-02-11",
                    date_livraison_prevue="2026-01-01",
                    nb_freins_actifs=0,
                    score_risque=15.3
                ),
                Operation(
                    id=8045,
                    numero="8045",
                    nom="Nérée Servant",
                    type_operation="OPP",
                    commune="Les Abymes",
                    statut_global="BLOQUE",
                    avancement_pct=32.0,
                    aco_responsable="MSL",
                    budget_initial=1890000,
                    rem_projetee=66150,
                    rem_generee=21168,
                    nb_logements_lls=15,
                    nb_logements_llts=9,
                    date_creation="2021-05-20",
                    date_livraison_prevue="2026-03-01",
                    nb_freins_actifs=1,
                    score_risque=78.4
                )
            ]
            
            self.calculate_portfolio_stats()
    
    def load_phases_data(self):
        """Charge les phases pour chaque opération"""
        if not st.session_state.phases:
            for operation in st.session_state.operations:
                if operation.type_operation == "OPP":
                    phases = OPPWorkflow.generer_phases_demo(operation.id, operation.avancement_pct)
                    st.session_state.phases[operation.id] = phases
    
    def load_freins_data(self):
        """Charge les freins actifs"""
        if not st.session_state.freins:
            # Frein sur Nérée Servant
            st.session_state.freins = [
                Frein(
                    id=1,
                    phase_id=8045015,  # Phase LBU de l'opération 8045
                    operation_id=8045,
                    titre="Retard validation LBU",
                    description="La LBU est en attente de validation par le conseil d'administration depuis 3 semaines.",
                    type_frein="ADMINISTRATIF",
                    statut_frein="OUVERT",
                    niveau_impact="FORT",
                    date_signalement=(datetime.now() - timedelta(days=21)).strftime("%Y-%m-%d"),
                    signale_par="MSL",
                    actions_correctives="Relancer le secrétariat pour programmation CA extraordinaire"
                )
            ]
    
    def calculate_portfolio_stats(self):
        """Calcule les statistiques du portfolio"""
        operations = st.session_state.operations
        
        st.session_state.portfolio_stats = {
            'nb_total': len(operations),
            'nb_actives': len([op for op in operations if op.est_active]),
            'nb_bloquees': len([op for op in operations if op.statut_global == "BLOQUE"]),
            'avancement_moyen': sum(op.avancement_pct for op in operations) / len(operations) if operations else 0,
            'rem_totale_projetee': sum(op.rem_projetee for op in operations),
            'rem_totale_generee': sum(op.rem_generee for op in operations),
            'budget_total': sum(op.budget_initial for op in operations),
            'nb_logements_total': sum(op.nb_logements_lls + op.nb_logements_llts + op.nb_logements_pls for op in operations),
            'nb_freins_total': sum(op.nb_freins_actifs for op in operations),
            'score_risque_moyen': sum(op.score_risque for op in operations) / len(operations) if operations else 0
        }

# ============================================================================
# COMPOSANTS STREAMLIT PERSONNALISÉS
# ============================================================================

def render_operation_status_badge(statut: str) -> str:
    """Retourne un badge coloré pour le statut"""
    colors = {
        "MONTAGE": "🟡",
        "APPEL_OFFRES": "🔵", 
        "TRAVAUX": "🟠",
        "LIVREE": "🟢",
        "BLOQUE": "🔴",
        "CLOTURE": "⚫"
    }
    return f"{colors.get(statut, '⚪')} {statut}"

def render_phase_status_badge(statut: str) -> str:
    """Badge pour le statut d'une phase"""
    colors = {
        "VALIDE": "🟢",
        "EN_COURS": "🔵",
        "EN_ATTENTE": "⚪",
        "FREIN": "🔴",
        "BLOQUE": "⚫"
    }
    return f"{colors.get(statut, '⚪')} {statut}"

def render_domaine_badge(domaine: str) -> str:
    """Badge pour le domaine d'une phase"""
    colors = {
        "OPERATIONNEL": "🔧",
        "JURIDIQUE": "⚖️",
        "BUDGETAIRE": "💰",
        "ADMINISTRATIF": "🏛️"
    }
    return f"{colors.get(domaine, '📋')} {domaine}"

# ============================================================================
# MODULES MÉTIER STREAMLIT
# ============================================================================

def render_med_manager():
    """Module de gestion des MED"""
    st.subheader("🚨 Gestion MED (Mise En Demeure)")
    
    # MED actives demo
    if st.session_state.current_operation_id == 8021:
        with st.expander("MED #1 - SARL BATIMENT CARAIBE (Active)", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Lot:** Gros Œuvre")
                st.write("**Objet:** Retard dans l'exécution des travaux")
                st.write("**Statut:** EMISE")
            with col2:
                st.write("**Émise le:** 08/12/2024")
                st.write("**Limite réponse:** 23/12/2024")
                st.error("⚠️ 7 jours restants")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("📄 Voir Document", key="med_doc"):
                    st.success("Document MED généré automatiquement")
            with col2:
                if st.button("📧 Relancer", key="med_relance"):
                    st.success("Relance envoyée")
            with col3:
                if st.button("✅ Résoudre", key="med_resolve"):
                    st.success("MED marquée comme résolue")
    else:
        st.success("✅ Aucune MED active sur cette opération")
    
    if st.button("➕ Créer une nouvelle MED"):
        st.info("Formulaire de création MED (à implémenter)")

def render_dgd_workflow():
    """Module workflow DGD"""
    st.subheader("📋 DGD (Dossier Garantie Décennale)")
    st.caption("Workflow 3 étapes réglementaires")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 1️⃣ Préparation Entreprise")
        st.write("📋 Collecte documents")
        st.write("⏰ Délai: 15 jours")
        if st.button("🚀 Démarrer DGD"):
            st.success("DGD démarrée - Entreprise notifiée")
    
    with col2:
        st.markdown("#### 2️⃣ Validation MOE")
        st.write("✅ Contrôle conformité")
        st.write("⏰ Délai: 10 jours max")
        st.info("En attente étape 1")
    
    with col3:
        st.markdown("#### 3️⃣ Validation MOA")
        st.write("📋 Validation finale SPIC")
        st.write("⏰ Délai: 30 jours max")
        st.info("En attente étapes précédentes")

def render_os_manager():
    """Module gestion des OS"""
    st.subheader("📝 Ordres de Service")
    
    # OS existants demo
    if st.session_state.current_operation_id == 8021:
        os_data = [
            {"numero": "OS-001-2024", "type": "DEMARRAGE", "destinataire": "SARL BATIMENT CARAIBE", "statut": "EXECUTE", "date": "15/10/2024"},
            {"numero": "OS-002-2024", "type": "MODIFICATION", "destinataire": "SARL BATIMENT CARAIBE", "statut": "EXECUTE", "date": "20/11/2024"},
            {"numero": "OS-003-2024", "type": "PENALITE", "destinataire": "SARL BATIMENT CARAIBE", "statut": "EN_ATTENTE", "date": "08/12/2024"}
        ]
        
        df_os = pd.DataFrame(os_data)
        st.dataframe(df_os, use_container_width=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕ Nouvel OS"):
                st.info("Formulaire création OS")
        with col2:
            if st.button("📥 Import GESPRO"):
                st.info("Importation depuis GESPRO en cours...")
        with col3:
            st.metric("OS en attente", "1")
    else:
        st.info("Aucun OS pour cette opération")

# ============================================================================
# INTERFACE PRINCIPALE
# ============================================================================

def render_sidebar():
    """Sidebar avec navigation et opération active"""
    with st.sidebar:
        st.image("https://via.placeholder.com/200x80/1E3A8A/FFFFFF?text=OPCOPILOT", 
                caption="Outil Central MOA - SPIC v2.0")
        
        st.markdown("---")
        
        # Informations utilisateur
        st.markdown(f"👤 **{st.session_state.user_nom}**")
        st.markdown(f"🎭 {st.session_state.user_role}")
        
        st.markdown("---")
        
        # Sélection opération active
        st.subheader("🎯 Opération Active")
        operations = st.session_state.operations
        operation_names = [f"{op.numero} - {op.nom}" for op in operations]
        
        if operations:
            if 'selected_operation_idx' not in st.session_state:
                st.session_state.selected_operation_idx = 0
            
            selected_idx = st.selectbox(
                "Choisir une opération",
                range(len(operations)),
                format_func=lambda i: operation_names[i],
                index=st.session_state.selected_operation_idx,
                key="operation_selector"
            )
            st.session_state.selected_operation_idx = selected_idx
            st.session_state.current_operation_id = operations[selected_idx].id
            current_operation = operations[selected_idx]
            
            # Détails opération sélectionnée
            st.markdown(f"**Type:** {current_operation.type_operation}")
            st.markdown(f"**Commune:** {current_operation.commune}")
            st.markdown(f"**ACO:** {current_operation.aco_responsable}")
            st.markdown(f"**Statut:** {render_operation_status_badge(current_operation.statut_global)}")
            
            # Barre d'avancement
            st.markdown("**Avancement:**")
            st.progress(current_operation.avancement_pct / 100)
            st.caption(f"{current_operation.avancement_pct:.1f}%")
            
            # Alertes
            if current_operation.nb_freins_actifs > 0:
                st.error(f"⚠️ {current_operation.nb_freins_actifs} frein(s) actif(s)")
            
            if current_operation.score_risque > 50:
                st.warning(f"🚨 Score risque: {current_operation.score_risque:.1f}/100")
        
        st.markdown("---")
        
        # Actions rapides
        st.subheader("⚡ Actions Rapides")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📝 Saisir REM", use_container_width=True):
                st.session_state.show_rem_form = True
        with col2:
            if st.button("🚨 Signaler Frein", use_container_width=True):
                st.session_state.show_frein_form = True
        
        if st.button("📊 Export SPIC", use_container_width=True):
            st.session_state.show_export = True

def render_dashboard_overview():
    """Onglet vue d'ensemble du portfolio"""
    
    st.subheader("📋 Portfolio des Opérations")
    
    # Métriques globales
    stats = st.session_state.portfolio_stats
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Opérations Portfolio",
            f"{stats['nb_actives']}/{stats['nb_total']}",
            f"+{stats['nb_actives'] - stats['nb_bloquees']} actives"
        )
    
    with col2:
        st.metric(
            "Avancement Moyen",
            f"{stats['avancement_moyen']:.1f}%"
        )
    
    with col3:
        rem_pct = (stats['rem_totale_generee'] / stats['rem_totale_projetee']) * 100 if stats['rem_totale_projetee'] > 0 else 0
        st.metric(
            "REM Portfolio 2024",
            f"{stats['rem_totale_generee']:,.0f}€",
            f"{rem_pct:.1f}% objectif"
        )
    
    with col4:
        st.metric(
            "Alertes Actives",
            stats['nb_freins_total'],
            f"Score risque: {stats['score_risque_moyen']:.1f}"
        )
    
    st.markdown("---")
    
    # Filtres
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_type = st.selectbox("Type", ["TOUS", "OPP", "VEFA", "MANDAT", "AMO"])
    with col2:
        filter_statut = st.selectbox("Statut", ["TOUS", "MONTAGE", "APPEL_OFFRES", "TRAVAUX", "LIVREE", "BLOQUE"])
    with col3:
        filter_aco = st.selectbox("ACO", ["TOUS", "MCA", "MSL", "LU", "ROS", "IF"])
    
    # Tableau des opérations
    operations = st.session_state.operations
    
    # Application des filtres
    if filter_type != "TOUS":
        operations = [op for op in operations if op.type_operation == filter_type]
    if filter_statut != "TOUS":
        operations = [op for op in operations if op.statut_global == filter_statut]
    if filter_aco != "TOUS":
        operations = [op for op in operations if op.aco_responsable == filter_aco]
    
    # Données pour le tableau
    df_data = []
    for op in operations:
        df_data.append({
            "N°": op.numero,
            "Nom": op.nom,
            "Type": op.type_operation,
            "Commune": op.commune,
            "Statut": op.statut_global,
            "ACO": op.aco_responsable,
            "Logements": op.nb_logements_lls + op.nb_logements_llts + op.nb_logements_pls,
            "Avancement": op.avancement_pct,
            "Budget (k€)": op.budget_initial/1000,
            "REM Générée (€)": op.rem_generee,
            "Freins": "🔴" if op.nb_freins_actifs > 0 else "🟢",
            "Risque": op.score_risque
        })
    
    if df_data:
        df = pd.DataFrame(df_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Avancement": st.column_config.ProgressColumn(
                    "Avancement",
                    help="Pourcentage d'avancement",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
                "REM Générée (€)": st.column_config.NumberColumn(
                    "REM Générée (€)",
                    help="REM générée à ce jour",
                    format="€%.0f"
                )
            }
        )
    else:
        st.info("Aucune opération ne correspond aux filtres sélectionnés.")

def render_timeline_interactive():
    """Timeline interactive de l'opération courante"""
    
    if st.session_state.current_operation_id:
        current_operation = next(op for op in st.session_state.operations 
                               if op.id == st.session_state.current_operation_id)
        
        st.subheader(f"📅 Timeline - {current_operation.nom}")
        st.caption(f"**Type:** {current_operation.type_operation} | **Avancement:** {current_operation.avancement_pct:.1f}%")
        
        # Filtres timeline
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_domaine = st.selectbox("Domaine", ["TOUS", "OPERATIONNEL", "JURIDIQUE", "BUDGETAIRE", "ADMINISTRATIF"], key="timeline_domaine")
        with col2:
            filter_statut_phase = st.selectbox("Statut Phase", ["TOUS", "EN_ATTENTE", "EN_COURS", "VALIDE", "FREIN"], key="timeline_statut")
        with col3:
            show_critiques_only = st.checkbox("Phases critiques uniquement")
        
        # Récupération des phases
        phases = st.session_state.phases.get(current_operation.id, [])
        
        # Application des filtres
        phases_filtrees = phases
        if filter_domaine != "TOUS":
            phases_filtrees = [p for p in phases_filtrees if p.domaine == filter_domaine]
        if filter_statut_phase != "TOUS":
            phases_filtrees = [p for p in phases_filtrees if p.statut == filter_statut_phase]
        if show_critiques_only:
            phases_filtrees = [p for p in phases_filtrees if p.est_critique]
        
        # Affichage timeline
        st.markdown("### 🔄 Workflow Chronologique")
        
        for phase in phases_filtrees:
            with st.container():
                col1, col2, col3, col4 = st.columns([1, 6, 2, 1])
                
                with col1:
                    st.markdown(f"**{phase.ordre}**")
                    st.markdown(render_phase_status_badge(phase.statut))
                
                with col2:
                    st.markdown(f"**{phase.nom}**")
                    if phase.est_critique:
                        st.markdown("⭐ *Phase critique*")
                    st.markdown(f"*{render_domaine_badge(phase.domaine)} - {phase.responsable_principal}*")
                    if phase.impact_rem:
                        st.markdown("💰 *Impact REM*")
                
                with col3:
                    st.markdown(f"**{phase.statut}**")
                    if phase.statut == "FREIN":
                        st.error("Frein actif")
                    elif phase.statut == "VALIDE":
                        st.success("Validée")
                
                with col4:
                    if phase.statut == "EN_COURS":
                        if st.button("✅", key=f"validate_{phase.id}", help="Valider cette phase"):
                            st.success(f"Phase {phase.ordre} validée !")
                            st.rerun()
                    elif phase.statut == "EN_ATTENTE":
                        if st.button("🚨", key=f"frein_{phase.id}", help="Signaler un frein"):
                            st.session_state.frein_phase_id = phase.id
                            st.session_state.show_frein_form = True
                
                st.divider()
        
        # Résumé timeline
        st.markdown("### 📊 Résumé Timeline")
        col1, col2, col3, col4 = st.columns(4)
        
        nb_validees = len([p for p in phases if p.statut == "VALIDE"])
        nb_en_cours = len([p for p in phases if p.statut == "EN_COURS"])
        nb_freins = len([p for p in phases if p.statut == "FREIN"])
        nb_attente = len([p for p in phases if p.statut == "EN_ATTENTE"])
        
        with col1:
            st.metric("Phases Validées", nb_validees)
        with col2:
            st.metric("En Cours", nb_en_cours)
        with col3:
            st.metric("Freins Actifs", nb_freins)
        with col4:
            st.metric("En Attente", nb_attente)
    
    else:
        st.info("Sélectionnez une opération dans la sidebar pour voir sa timeline.")

def render_modules_metier():
    """Onglet modules métier spécialisés"""
    
    st.subheader("🔧 Modules Métier Spécialisés")
    
    # Sous-onglets pour les modules
    tab_med, tab_dgd, tab_os = st.tabs(["🚨 MED", "📋 DGD", "📝 OS"])
    
    with tab_med:
        render_med_manager()
    
    with tab_dgd:
        render_dgd_workflow()
    
    with tab_os:
        render_os_manager()

def render_analytics_dashboard():
    """Onglet analytics et rapports"""
    
    st.subheader("📈 Analytics & Pilotage")
    
    # Dashboard managérial - 4 dimensions
    st.markdown("### 🎯 Pilotage 4 Dimensions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Dimension Administrative
        with st.container():
            st.markdown("#### 🏛️ Administrative")
            score_admin = 72
            color = "🟡" if score_admin < 80 else "🟢"
            st.markdown(f"{color} Score: **{score_admin}/100**")
            st.markdown("- 8 autorisations en cours")
            st.markdown("- 2 PC en retard d'instruction")
            st.warning("1 LBU en attente validation CA")
        
        # Dimension Financière  
        with st.container():
            st.markdown("#### 💰 Financière")
            score_finance = 85
            color = "🟢" if score_finance >= 80 else "🟡"
            st.markdown(f"{color} Score: **{score_finance}/100**")
            st.markdown("- 21 budgets respectés")
            st.markdown("- 99.4% REM vs objectif")
            st.success("Performance financière excellente")
    
    with col2:
        # Dimension Juridique
        with st.container():
            st.markdown("#### ⚖️ Juridique")
            score_juridique = 88
            color = "🟢" if score_juridique >= 80 else "🟡"
            st.markdown(f"{color} Score: **{score_juridique}/100**")
            st.markdown("- 15 marchés signés")
            st.markdown("- 0 litige actif")
            st.success("Conformité juridique excellente")
        
        # Dimension Opérationnelle
        with st.container():
            st.markdown("#### 🔧 Opérationnelle")
            score_ops = 68
            color = "🟡" if score_ops < 80 else "🟢"
            st.markdown(f"{color} Score: **{score_ops}/100**")
            st.markdown("- 18 chantiers conformes")
            st.markdown("- 3 chantiers en retard")
            st.warning("Contrôles qualité à renforcer")
    
    # TOP 3 Risques
    st.markdown("### 🚨 TOP 3 Risques Portfolio")
    
    risques = [
        {"rang": 1, "operation": "Nérée Servant", "score": 78.4, "type": "ADMINISTRATIF", "description": "Blocage LBU depuis 3 semaines"},
        {"rang": 2, "operation": "Cour Charneau", "score": 45.2, "type": "OPERATIONNEL", "description": "Retard entreprise gros œuvre"},
        {"rang": 3, "operation": "Zonis ZB1", "score": 22.1, "type": "FINANCIER", "description": "Révision budget études"}
    ]
    
    for risque in risques:
        with st.expander(f"🚨 Risque #{risque['rang']} - {risque['operation']} (Score: {risque['score']:.1f})"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Type:** {risque['type']}")
                st.markdown(f"**Description:** {risque['description']}")
            with col2:
                st.markdown(f"**Score Risque:** {risque['score']:.1f}/100")
                if st.button(f"🎯 Plan d'action", key=f"action_{risque['rang']}"):
                    st.info(f"Plan d'action généré pour {risque['operation']}")

# ============================================================================
# APPLICATION PRINCIPALE
# ============================================================================

def main():
    """Application principale OPCOPILOT Streamlit"""
    
    # Initialisation
    data_manager = DataManager()
    
    # Sidebar
    render_sidebar()
    
    # Contenu principal
    st.title("🏗️ OPCOPILOT - Dashboard Central")
    st.markdown("*Outil Central de Maîtrise d'Ouvrage - SPIC Guadeloupe*")
    
    # Onglets principaux
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Vue d'ensemble", "📅 Timeline", "🔧 Modules Métier", "📈 Analytics"])
    
    with tab1:
        render_dashboard_overview()
    
    with tab2:
        render_timeline_interactive()
    
    with tab3:
        render_modules_metier()
    
    with tab4:
        render_analytics_dashboard()

if __name__ == "__main__":
    main()
