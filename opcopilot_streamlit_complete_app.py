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
            cursor.execute("SELECT * FROM phases WHERE operation_id = ?", (op_data[0],))
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

# Templates de phases par type d'opération
TEMPLATES_PHASES = {
    "OPP": [
        {"nom": "Étude de Faisabilité", "duree_jours": 30, "couleur": "#2ca02c"},
        {"nom": "Montage Financier", "duree_jours": 45, "couleur": "#1f77b4"},
        {"nom": "Permis de Construire", "duree_jours": 90, "couleur": "#ff7f0e"},
        {"nom": "Consultation Entreprises", "duree_jours": 60, "couleur": "#d62728"},
        {"nom": "Attribution Marchés", "duree_jours": 30, "couleur": "#9467bd"},
        {"nom": "Travaux Terrassement", "duree_jours": 45, "couleur": "#8c564b"},
        {"nom": "Travaux Gros Œuvre", "duree_jours": 120, "couleur": "#e377c2"},
        {"nom": "Travaux Second Œuvre", "duree_jours": 90, "couleur": "#7f7f7f"},
        {"nom": "Réception Travaux", "duree_jours": 15, "couleur": "#bcbd22"},
        {"nom": "Livraison", "duree_jours": 30, "couleur": "#17becf"}
    ],
    "VEFA": [
        {"nom": "Sélection Promoteur", "duree_jours": 60, "couleur": "#2ca02c"},
        {"nom": "Négociation Contrat", "duree_jours": 30, "couleur": "#1f77b4"},
        {"nom": "Signature VEFA", "duree_jours": 15, "couleur": "#ff7f0e"},
        {"nom": "Suivi Travaux", "duree_jours": 365, "couleur": "#d62728"},
        {"nom": "Pré-réception", "duree_jours": 15, "couleur": "#9467bd"},
        {"nom": "Réception Définitive", "duree_jours": 30, "couleur": "#8c564b"}
    ],
    "MANDATS_ETUDES": [
        {"nom": "Définition Mission", "duree_jours": 15, "couleur": "#2ca02c"},
        {"nom": "Consultation MOE", "duree_jours": 45, "couleur": "#1f77b4"},
        {"nom": "Attribution MOE", "duree_jours": 20, "couleur": "#ff7f0e"},
        {"nom": "Études AVP", "duree_jours": 60, "couleur": "#d62728"},
        {"nom": "Études PRO", "duree_jours": 90, "couleur": "#9467bd"},
        {"nom": "Livraison Études", "duree_jours": 15, "couleur": "#8c564b"}
    ],
    "MANDATS_REALISATION": [
        {"nom": "Reprise Études", "duree_jours": 30, "couleur": "#2ca02c"},
        {"nom": "Consultation Entreprises", "duree_jours": 60, "couleur": "#1f77b4"},
        {"nom": "Attribution Marchés", "duree_jours": 30, "couleur": "#ff7f0e"},
        {"nom": "Travaux", "duree_jours": 300, "couleur": "#d62728"},
        {"nom": "Réception", "duree_jours": 30, "couleur": "#9467bd"}
    ],
    "AMO": [
        {"nom": "Diagnostic Initial", "duree_jours": 20, "couleur": "#2ca02c"},
        {"nom": "Assistance Programmation", "duree_jours": 45, "couleur": "#1f77b4"},
        {"nom": "Assistance Consultation", "duree_jours": 60, "couleur": "#ff7f0e"},
        {"nom": "Assistance Réalisation", "duree_jours": 200, "couleur": "#d62728"},
        {"nom": "Bilan Mission", "duree_jours": 15, "couleur": "#9467bd"}
    ]
}

# Initialisation de la base de données
@st.cache_resource
def get_database():
    return DatabaseManager()

def create_timeline_gantt(operation: Operation):
    """Crée une timeline Gantt horizontale avec flèches colorées"""
    if not operation.phases:
        st.warning("Aucune phase définie pour cette opération")
        return
    
    fig = go.Figure()
    
    # Créer les barres pour chaque phase
    for i, phase in enumerate(operation.phases):
        # Calculer la durée en jours
        duration = (phase.date_fin - phase.date_debut).days
        
        # Couleur selon le statut
        color = phase.couleur
        if phase.statut == "Terminé":
            color = "#28a745"
        elif phase.statut == "En cours":
            color = "#007bff"
        elif phase.statut == "Retard":
            color = "#dc3545"
        
        # Ajouter la barre de la phase
        fig.add_trace(go.Bar(
            name=phase.nom,
            x=[duration],
            y=[phase.nom],
            orientation='h',
            marker=dict(
                color=color,
                line=dict(color='white', width=2)
            ),
            base=phase.date_debut,
            text=f"{phase.nom}<br>{duration} jours",
            textposition="inside",
            textfont=dict(color="white", size=10),
            hovertemplate=(
                f"<b>{phase.nom}</b><br>"
                f"Début: {phase.date_debut.strftime('%d/%m/%Y')}<br>"
                f"Fin: {phase.date_fin.strftime('%d/%m/%Y')}<br>"
                f"Durée: {duration} jours<br>"
                f"Statut: {phase.statut}<br>"
                f"Responsable: {phase.responsable}<br>"
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
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="#666666"
            )
    
    # Configuration du layout
    fig.update_layout(
        title=f"Timeline - {operation.nom}",
        xaxis_title="Période",
        yaxis_title="Phases",
        height=max(400, len(operation.phases) * 60),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            type='date',
            tickformat='%b %Y',
            gridcolor='lightgray',
            gridwidth=1
        ),
        yaxis=dict(
            gridcolor='lightgray',
            gridwidth=1
        ),
        margin=dict(l=200, r=50, t=50, b=50)
    )
    
    return fig

def dashboard():
    """Dashboard principal avec KPIs et vue d'ensemble"""
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
        st.metric(
            label="⚠️ Phases en Retard",
            value=phases_en_retard,
            delta="Critique" if phases_en_retard > 5 else "Normal",
            delta_color="inverse"
        )
    
    # Graphiques de suivi
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
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_layout(height=300)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Aucune opération créée")
    
    with col2:
        st.subheader("📊 Évolution des Budgets")
        if operations:
            # Créer un DataFrame pour l'évolution des budgets
            budget_data = []
            for op in operations:
                budget_data.append({
                    'Date': op.date_creation,
                    'Budget': op.budget,
                    'Type': op.type_operation
                })
            
            df_budget = pd.DataFrame(budget_data)
            df_budget = df_budget.sort_values('Date')
            df_budget['Budget_Cumulé'] = df_budget['Budget'].cumsum()
            
            fig_line = px.line(
                df_budget, 
                x='Date', 
                y='Budget_Cumulé',
                title="Évolution Cumulative des Budgets"
            )
            fig_line.update_layout(height=300)
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Aucune donnée budgétaire")
    
    # Tableau des opérations récentes
    st.subheader("📋 Opérations Récentes")
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
            progress = f"{phases_completed}/{phases_count}" if phases_count > 0 else "0/0"
            
            data.append({
                "Nom": op.nom,
                "Type": op.type_operation,
                "ACO": op.aco_responsable,
                "Statut": op.statut,
                "Budget": f"{op.budget:,.0f} €",
                "Progression": progress,
                "Créée le": op.date_creation.strftime("%d/%m/%Y")
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=400)
    else:
        st.info("Aucune opération trouvée. Utilisez le module 'Nouvelle Opération' pour commencer.")
    
    # Alertes et notifications
    st.subheader("🚨 Alertes & Notifications")
    
    alerts = []
    for op in operations:
        for phase in op.phases:
            if phase.statut == "Retard":
                alerts.append(f"⚠️ **{op.nom}** - Phase '{phase.nom}' en retard")
            if phase.freins:
                alerts.append(f"🛑 **{op.nom}** - Freins sur phase '{phase.nom}': {', '.join(phase.freins)}")
    
    if alerts:
        for alert in alerts[:5]:  # Afficher max 5 alertes
            st.error(alert)
    else:
        st.success("✅ Aucune alerte critique")

def nouvelle_operation():
    """Module de création d'une nouvelle opération"""
    st.header("➕ Nouvelle Opération")
    
    with st.form("nouvelle_operation"):
        col1, col2 = st.columns(2)
        
        with col1:
            nom = st.text_input("Nom de l'opération *", placeholder="Ex: Résidence Les Flamboyants")
            type_operation = st.selectbox(
                "Type d'opération *",
                ["OPP", "VEFA", "MANDATS_ETUDES", "MANDATS_REALISATION", "AMO"]
            )
            aco_responsable = st.selectbox(
                "ACO Responsable *",
                ["Jean MARTIN", "Marie DUBOIS", "Pierre BERNARD", "Sophie LEROY", "Michel PETIT"]
            )
        
        with col2:
            budget = st.number_input("Budget (€) *", min_value=0.0, value=100000.0, step=10000.0)
            date_debut = st.date_input("Date de début *", datetime.now().date())
            date_fin = st.date_input("Date de fin prévue *", (datetime.now() + timedelta(days=365)).date())
        
        # Personnalisation des phases
        st.subheader("🎯 Configuration des Phases")
        
        # Phases par défaut selon le type
        if type_operation in TEMPLATES_PHASES:
            st.info(f"Template {type_operation} : {len(TEMPLATES_PHASES[type_operation])} phases par défaut")
            
            # Afficher les phases du template
            with st.expander("Voir les phases du template"):
                for i, phase_template in enumerate(TEMPLATES_PHASES[type_operation]):
                    st.write(f"{i+1}. **{phase_template['nom']}** - {phase_template['duree_jours']} jours")
        
        # Option pour personnaliser
        personnaliser = st.checkbox("Personnaliser les phases")
        phases_personnalisees = []
        
        if personnaliser:
            st.write("Ajoutez vos phases personnalisées :")
            nb_phases = st.number_input("Nombre de phases", min_value=1, max_value=20, value=3)
            
            for i in range(nb_phases):
                with st.container():
                    col_nom, col_duree, col_couleur = st.columns([3, 1, 1])
                    with col_nom:
                        phase_nom = st.text_input(f"Phase {i+1}", key=f"phase_nom_{i}")
                    with col_duree:
                        phase_duree = st.number_input(f"Durée (j)", min_value=1, value=30, key=f"phase_duree_{i}")
                    with col_couleur:
                        phase_couleur = st.color_picker("Couleur", "#1f77b4", key=f"phase_couleur_{i}")
                    
                    if phase_nom:
                        phases_personnalisees.append({
                            "nom": phase_nom,
                            "duree_jours": phase_duree,
                            "couleur": phase_couleur
                        })
        
        submitted = st.form_submit_button("🚀 Créer l'Opération", type="primary")
        
        if submitted:
            if not nom or not type_operation or not aco_responsable:
                st.error("Veuillez remplir tous les champs obligatoires (*)")
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
                date_fin_phase = current_date + timedelta(days=phase_template["duree_jours"])
                
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
            db = get_database()
            db.save_operation(operation)
            
            st.success(f"✅ Opération '{nom}' créée avec succès !")
            st.balloons()
            
            # Afficher un aperçu de la timeline
            st.subheader("📊 Aperçu de la Timeline")
            fig = create_timeline_gantt(operation)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

def timeline_gantt():
    """Module timeline Gantt interactive"""
    st.header("📊 Timeline Gantt Interactive")
    
    db = get_database()
    operations = db.load_operations()
    
    if not operations:
        st.warning("Aucune opération trouvée. Créez d'abord une opération.")
        return
    
    # Sélection de l'opération
    operation_names = [f"{op.nom} ({op.type_operation})" for op in operations]
    selected_name = st.selectbox("Sélectionner une opération", operation_names)
    
    if selected_name:
        # Trouver l'opération sélectionnée
        selected_operation = None
        for op in operations:
            if f"{op.nom} ({op.type_operation})" == selected_name:
                selected_operation = op
                break
        
        if selected_operation:
            # Informations de l'opération
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Type", selected_operation.type_operation)
            with col2:
                st.metric("ACO", selected_operation.aco_responsable)
            with col3:
                st.metric("Budget", f"{selected_operation.budget:,.0f} €")
            
            # Timeline Gantt
            st.subheader("🎯 Timeline Interactive")
            fig = create_timeline_gantt(selected_operation)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            # Gestion des phases
            st.subheader("⚙️ Gestion des Phases")
            
            tabs = st.tabs(["📋 Liste des Phases", "➕ Ajouter Phase", "🔧 Modifier Phase"])
            
            with tabs[0]:
                # Liste des phases
                for i, phase in enumerate(selected_operation.phases):
                    with st.expander(f"{i+1}. {phase.nom} ({phase.statut})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Début :** {phase.date_debut.strftime('%d/%m/%Y')}")
                            st.write(f"**Fin :** {phase.date_fin.strftime('%d/%m/%Y')}")
                            st.write(f"**Durée :** {(phase.date_fin - phase.date_debut).days} jours")
                        with col2:
                            st.write(f"**Statut :** {phase.statut}")
                            st.write(f"**Responsable :** {phase.responsable}")
                            if phase.freins:
                                st.write(f"**Freins :** {', '.join(phase.freins)}")
                        
                        if phase.description:
                            st.write(f"**Description :** {phase.description}")
            
            with tabs[1]:
                # Ajouter une nouvelle phase
                st.write("Ajouter une nouvelle phase à l'opération")
                
                with st.form("add_phase"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_phase_nom = st.text_input("Nom de la phase")
                        new_phase_duree = st.number_input("Durée (jours)", min_value=1, value=30)
                    with col2:
                        new_phase_responsable = st.text_input("Responsable", value=selected_operation.aco_responsable)
                        new_phase_couleur = st.color_picker("Couleur", "#1f77b4")
                    
                    new_phase_description = st.text_area("Description (optionnel)")
                    
                    # Position d'insertion
                    positions = ["À la fin"] + [f"Avant '{phase.nom}'" for phase in selected_operation.phases]
                    position = st.selectbox("Insérer", positions)
                    
                    if st.form_submit_button("Ajouter la Phase"):
                        if new_phase_nom:
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
                            
                            date_fin = date_debut + timedelta(days=new_phase_duree)
                            
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
                            
                            # Sauvegarder
                            db.save_operation(selected_operation)
                            st.success("Phase ajoutée avec succès !")
                            st.rerun()
            
            with tabs[2]:
                # Modifier une phase existante
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
                                
                                # Gestion des freins
                                st.write("**Freins identifiés :**")
                                freins_actuels = selected_phase.freins.copy()
                                
                                # Afficher les freins existants
                                for i, frein in enumerate(freins_actuels):
                                    col_frein, col_del = st.columns([4, 1])
                                    with col_frein:
                                        st.write(f"• {frein}")
                                    with col_del:
                                        if st.checkbox("Suppr.", key=f"del_frein_{i}"):
                                            freins_actuels.remove(frein)
                                
                                # Ajouter nouveau frein
                                nouveau_frein = st.text_input("Ajouter un frein")
                                if nouveau_frein and nouveau_frein not in freins_actuels:
                                    freins_actuels.append(nouveau_frein)
                                
                                if st.form_submit_button("Modifier la Phase"):
                                    # Mettre à jour la phase
                                    selected_phase.statut = mod_statut
                                    selected_phase.responsable = mod_responsable
                                    selected_phase.date_debut = datetime.combine(mod_date_debut, datetime.min.time())
                                    selected_phase.date_fin = datetime.combine(mod_date_fin, datetime.min.time())
                                    selected_phase.description = mod_description
                                    selected_phase.freins = freins_actuels
                                    
                                    # Sauvegarder
                                    db.save_operation(selected_operation)
                                    st.success("Phase modifiée avec succès !")
                                    st.rerun()

def main():
    """Fonction principale avec navigation"""
    
    # Sidebar avec navigation
    st.sidebar.markdown("""
        <div class="sidebar-logo">
            <h2>🏗️ OPCOPILOT</h2>
            <p>SPIC Guadeloupe v3.0</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Menu de navigation
    pages = {
        "🏠 Dashboard": dashboard,
        "➕ Nouvelle Opération": nouvelle_operation,
        "📊 Timeline Gantt": timeline_gantt
    }
    
    selected_page = st.sidebar.selectbox("Navigation", list(pages.keys()))
    
    # Informations système dans la sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Modules Disponibles")
    modules = [
        "✅ Dashboard KPIs",
        "✅ Création Opération", 
        "✅ Timeline Gantt",
        "🔄 Gestion ACO (v3.1)",
        "🔄 Freins & Alertes (v3.1)",
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
    st.sidebar.info("OPCOPILOT v3.0 ALPHA\nTimeline + Opérations\nMars 2025")
    
    # Exécuter la page sélectionnée
    pages[selected_page]()

if __name__ == "__main__":
    main()
