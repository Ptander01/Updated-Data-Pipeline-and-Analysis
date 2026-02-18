"""
PM Dashboard Generator
Reads Patrick's Excel Work Organizer and generates a unified HTML dashboard.

Usage:
    python generate_pm_dashboard.py

Output:
    - PM_DASHBOARD.html (current dashboard)
    - archive/PM_DASHBOARD_YYYYMMDD.html (dated backup)

Author: Patrick Anderson / AI Assistant
Created: January 12, 2026
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import warnings

warnings.filterwarnings('ignore', category=UserWarning)

# =============================================================================
# CONFIGURATION
# =============================================================================

EXCEL_PATH = Path(r"C:\Users\ptanderson\Downloads\Patrick_Work_Organizer_Hierarchy (version 1).xlsb.xlsx")
OUTPUT_DIR = Path(__file__).parent if '__file__' in dir() else Path(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\00_docs\pm")
ARCHIVE_DIR = OUTPUT_DIR / "archive"
GDRIVE_OUTPUT = Path(r"G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\dashboards")
SESSION_LOG_PATH = Path(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\00_docs\context\SESSION_LOG.md")
ROLLING_WEEKS = 8  # Number of weeks for trend chart

PROJECT_CONFIG = {
    "SatelliteImagery": {"display_name": "Satellite Imagery", "icon": "🛰️", "color": "#9b59b6"},
    "GlobalDataCenter": {"display_name": "Global Data Center & Infra Model", "icon": "🏢", "color": "#4facfe"},
    "AdHoc": {"display_name": "Ad Hoc / To Dos", "icon": "📋", "color": "#00d68f"}
}

# =============================================================================
# GSD TASK HIERARCHY (from Meta Task GSD)
# =============================================================================
GSD_TASKS = {
    "Global Data Center & Infra Model": {
        "icon": "🏢",
        "sections": {
            "0. Documentation and PM": {
                "status": "ongoing",
                "tasks": []
            },
            "1. Current Data Sources (Live)": {
                "status": "complete",
                "tasks": []
            },
            "2. Synthesize Datasets (future)": {
                "status": "in_progress",
                "tasks": [
                    {"name": "Publish Consensus Table to Portal", "status": "planned"},
                    {"name": "Improve Report Card", "status": "in_progress"},
                    {"name": "Audit Woodmac", "status": "planned"},
                    {"name": "Audit Synergy", "status": "planned"},
                    {"name": "SemiAnalysis", "status": "in_progress", "subtasks": [
                        {"name": "AI Labs - OpenAI, Anthropic etc", "status": "in_progress"},
                        {"name": "Clean AI model", "status": "in_progress"},
                        {"name": "Update Data Vintage", "status": "in_progress"},
                        {"name": "Automate Data Cleaning process", "status": "planned"}
                    ]}
                ]
            },
            "3. Dashboard Functionality/UI": {
                "status": "planned",
                "tasks": []
            }
        }
    }
}

# =============================================================================
# ACCOMPLISHMENTS (Extracted from AI_CONTEXT_PROMPT.md & SESSION_LOG.md)
# =============================================================================
ACCOMPLISHMENTS = [
    # January 2026 - Recent Work
    {
        "date": "Jan 13, 2026",
        "category": "Web Dashboard",
        "title": "Map Symbology Overhaul (Session 21)",
        "description": "Removed clustering, added zoom-based Campus/Building visibility, fixed-size points, grayscale status rings, removed visual clutter (essential indicator, hyperscaler highlights)",
        "status": "complete"
    },
    {
        "date": "Jan 13, 2026",
        "category": "Web Dashboard",
        "title": "Essential Sites Filter Fix + /api/reload",
        "description": "Fixed Essential Sites filter (was returning 0 results), added /api/reload endpoint to refresh backend cache without restart",
        "status": "complete"
    },
    {
        "date": "Jan 13, 2026",
        "category": "Infrastructure",
        "title": "Node.js v24.13.0 Installation",
        "description": "Installed Node.js LTS for Vite frontend development server, npm dependencies installed",
        "status": "complete"
    },
    {
        "date": "Jan 13, 2026",
        "category": "Web Dashboard",
        "title": "Dashboard UI Enhancements (Session 20)",
        "description": "Rebranded to 'Global Data Center Locations - Consensus Model', added capacity type selector, redesigned source filter with 'contains' logic, updated company colors per brand guidelines, fixed legend duplicates",
        "status": "complete"
    },
    {
        "date": "Jan 13, 2026",
        "category": "Pipeline Validation",
        "title": "Full Pipeline Run + Essential DC Validation",
        "description": "Ran complete pipeline in 7.1 minutes, confirmed 127 buildings marked Essential, validated 22,696 buildings and 11,561 campuses",
        "status": "complete"
    },
    {
        "date": "Jan 12, 2026",
        "category": "PM & Documentation",
        "title": "PM Dashboard Generator",
        "description": "Built automated PM dashboard system with Excel integration, 8-week trend charts, and Google Drive sync",
        "status": "complete"
    },
    {
        "date": "Jan 11, 2026",
        "category": "SemiAnalysis Integration",
        "title": "SemiAnalysis Data Quality Audit",
        "description": "Comprehensive audit of SemiAnalysis Excel data: analyzed 19 columns, identified UCID mapping issues, documented AI Labs coverage",
        "status": "complete"
    },
    {
        "date": "Jan 10, 2026",
        "category": "Pipeline Enhancement",
        "title": "Essential DC List Integration",
        "description": "Integrated Essential DC List dataset into gold layer with UCID joins and temporal metadata",
        "status": "complete"
    },
    {
        "date": "Jan 9, 2026",
        "category": "Schema Design",
        "title": "XB Schema v3.0 Optimization",
        "description": "Redesigned XB table with 40 core columns, improved join performance, added consensus_strength metrics",
        "status": "complete"
    },
    {
        "date": "Jan 8, 2026",
        "category": "Automation",
        "title": "Nightly Sync Script",
        "description": "Created automated nightly sync with smart change detection, conflict resolution, and audit logging",
        "status": "complete"
    },
    # December 2025 - Major Milestones
    {
        "date": "Dec 2025",
        "category": "Report Card",
        "title": "Executive Report Card v2.0",
        "description": "Interactive HTML report with consensus strength scoring, temporal freshness section, and source agreement matrices",
        "status": "complete"
    },
    {
        "date": "Dec 2025",
        "category": "Schema Design",
        "title": "UCID v2.0 Redesign",
        "description": "Implemented new UCID format (building/campus codes), eliminated legacy issues, improved 3,000+ linkages",
        "status": "complete"
    },
    {
        "date": "Dec 2025",
        "category": "Data Integration",
        "title": "Meta Canonical Integration",
        "description": "Integrated 4,200 Meta-owned sites from canonical source as authoritative baseline",
        "status": "complete"
    },
    {
        "date": "Dec 2025",
        "category": "Pipeline Architecture",
        "title": "Scripts Reorganization",
        "description": "Restructured codebase with modular organization, shared utilities, and Google Drive integration",
        "status": "complete"
    },
    {
        "date": "Dec 2025",
        "category": "Data Processing",
        "title": "Gold Layer Standardization",
        "description": "Standardized all 6 source datasets into consistent schema with 22,696 buildings and 11,715 campuses",
        "status": "complete"
    },
    {
        "date": "Dec 2025",
        "category": "XB Table",
        "title": "Consensus XB Table",
        "description": "Built cross-reference table with 34,411 records linking all sources via UCID with source_count metrics",
        "status": "complete"
    },
    {
        "date": "Nov 2025",
        "category": "Project Initiation",
        "title": "Pipeline Architecture Design",
        "description": "Designed bronze-silver-gold medallion architecture for data quality and source attribution",
        "status": "complete"
    }
]

# =============================================================================
# DATA LOADING
# =============================================================================

def load_excel_data():
    """Load all sheets from the Excel workbook."""
    xl = pd.ExcelFile(EXCEL_PATH)
    data = {
        'tasks': pd.read_excel(xl, sheet_name='Tasks'),
        'time_log': pd.read_excel(xl, sheet_name='Time Log'),
        'reference': pd.read_excel(xl, sheet_name='Reference Lists'),
    }
    # Clean up tasks - only rows with Task ID AND Title (exclude empty template rows)
    data['tasks'] = data['tasks'][
        (data['tasks']['Task ID'].notna()) &
        (data['tasks']['Title'].notna())
    ].copy()

    # Clean up time log - only rows with Date
    data['time_log'] = data['time_log'][data['time_log']['Date'].notna()].copy()
    data['time_log']['Date'] = pd.to_datetime(data['time_log']['Date'])
    return data

def calculate_week_dates():
    """Calculate current and previous week date ranges."""
    today = datetime.now()
    days_since_monday = today.weekday()
    current_week_start = today - timedelta(days=days_since_monday)
    current_week_start = current_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    current_week_end = current_week_start + timedelta(days=6)
    prev_week_start = current_week_start - timedelta(days=7)
    prev_week_end = prev_week_start + timedelta(days=6)
    return {
        'current': (current_week_start, current_week_end),
        'previous': (prev_week_start, prev_week_end),
        'today': today
    }

# =============================================================================
# METRICS CALCULATION
# =============================================================================

def calculate_metrics(data, week_dates):
    """Calculate all dashboard metrics."""
    tasks = data['tasks']
    time_log = data['time_log']
    current_start, current_end = week_dates['current']
    prev_start, prev_end = week_dates['previous']

    current_week_time = time_log[(time_log['Date'] >= current_start) & (time_log['Date'] <= current_end)]
    prev_week_time = time_log[(time_log['Date'] >= prev_start) & (time_log['Date'] <= prev_end)]

    metrics = {
        'total_tasks': len(tasks),
        'tasks_in_progress': len(tasks[tasks['Status'] == 'In Progress']),
        'tasks_blocked': len(tasks[tasks['Status'] == 'Blocked']),
        'tasks_complete': len(tasks[tasks['Status'] == 'Complete']),
        'scope_changes': len(tasks[tasks['Scope Change'].isin(['Added', 'Reduced'])]),
        'current_week_hours': current_week_time['Hours'].sum() if len(current_week_time) > 0 else 0,
        'prev_week_hours': prev_week_time['Hours'].sum() if len(prev_week_time) > 0 else 0,
        'total_hours_logged': time_log['Hours'].sum(),
        'hours_by_project': {},
        'tasks_by_project': {},
        'daily_hours': {}
    }

    for parent_code, config in PROJECT_CONFIG.items():
        project_time = current_week_time[current_week_time['Parent (auto)'] == config['display_name']]
        metrics['hours_by_project'][parent_code] = project_time['Hours'].sum() if len(project_time) > 0 else 0
        project_tasks = tasks[tasks['Parent Category'] == config['display_name']]
        metrics['tasks_by_project'][parent_code] = {
            'total': len(project_tasks),
            'in_progress': len(project_tasks[project_tasks['Status'] == 'In Progress']),
            'complete': len(project_tasks[project_tasks['Status'] == 'Complete']),
            'blocked': len(project_tasks[project_tasks['Status'] == 'Blocked'])
        }

    for i in range(7):
        day_date = current_start + timedelta(days=i)
        day_name = day_date.strftime('%a')
        day_time = current_week_time[current_week_time['Date'].dt.date == day_date.date()]
        metrics['daily_hours'][day_name] = {
            'date': day_date.strftime('%Y-%m-%d'),
            'total': day_time['Hours'].sum() if len(day_time) > 0 else 0,
            'by_project': {}
        }
        for parent_code, config in PROJECT_CONFIG.items():
            project_time = day_time[day_time['Parent (auto)'] == config['display_name']]
            metrics['daily_hours'][day_name]['by_project'][parent_code] = project_time['Hours'].sum() if len(project_time) > 0 else 0

    return metrics

def calculate_subcategory_hours(data, week_dates):
    """Calculate hours by subcategory for current week."""
    time_log = data['time_log']
    current_start, current_end = week_dates['current']
    current_week_time = time_log[(time_log['Date'] >= current_start) & (time_log['Date'] <= current_end)]

    subcategory_hours = {}
    for parent_code, config in PROJECT_CONFIG.items():
        project_time = current_week_time[current_week_time['Parent (auto)'] == config['display_name']]
        if len(project_time) > 0:
            subcategory_hours[parent_code] = project_time.groupby('Subcategory (auto)')['Hours'].sum().to_dict()
        else:
            subcategory_hours[parent_code] = {}
    return subcategory_hours

def get_blocked_tasks(data):
    return data['tasks'][data['tasks']['Status'] == 'Blocked']

def get_scope_changes(data):
    return data['tasks'][data['tasks']['Scope Change'].isin(['Added', 'Reduced'])]

def get_active_tasks(data, limit=15):
    tasks = data['tasks']
    active = tasks[tasks['Status'].isin(['In Progress', 'Blocked', 'Planned'])].copy()
    priority_order = {'P1 - Critical': 0, 'P2 - High': 1, 'P3 - Medium': 2, 'P4 - Low': 3}
    status_order = {'Blocked': 0, 'In Progress': 1, 'Planned': 2}
    if len(active) > 0:
        active['priority_sort'] = active['Priority'].map(priority_order).fillna(4)
        active['status_sort'] = active['Status'].map(status_order).fillna(3)
        active = active.sort_values(['status_sort', 'priority_sort'])
    return active.head(limit)

def get_subcategories_for_project(data, parent_code):
    reference = data['reference']
    if parent_code in reference.columns:
        subcats = reference[parent_code].dropna().tolist()
        if subcats:
            return subcats
    config = PROJECT_CONFIG.get(parent_code, {})
    display_name = config.get('display_name', '')
    tasks = data['tasks']
    project_tasks = tasks[tasks['Parent Category'] == display_name]
    return project_tasks['Subcategory'].dropna().unique().tolist()

def get_heat_class(hours):
    if hours == 0: return "heat-0"
    elif hours < 1: return "heat-1"
    elif hours < 2: return "heat-2"
    elif hours < 4: return "heat-3"
    elif hours < 6: return "heat-4"
    else: return "heat-5"

def load_session_logs(limit=3):
    """Load recent session logs from SESSION_LOG.md."""
    sessions = []
    if not SESSION_LOG_PATH.exists():
        return sessions

    try:
        with open(SESSION_LOG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse sessions (## Session: headers)
        import re
        session_pattern = r'## Session: ([^\n]+)\n\n\*\*Focus:\*\* ([^\n]+)\n\n### Summary\n([^\n]+(?:\n(?!##)[^\n]*)*)'
        matches = re.findall(session_pattern, content, re.MULTILINE)

        for match in matches[:limit]:
            date_str, focus, summary = match
            sessions.append({
                'date': date_str.strip(),
                'focus': focus.strip(),
                'summary': summary.strip().split('\n')[0][:200]  # First line, max 200 chars
            })
    except Exception as e:
        print(f"      [WARN] Could not parse session log: {e}")

    return sessions

def calculate_rolling_weeks(data, num_weeks=8):
    """Calculate hours by project for the last N weeks."""
    time_log = data['time_log']
    today = datetime.now()

    # Find Monday of current week
    days_since_monday = today.weekday()
    current_week_start = today - timedelta(days=days_since_monday)
    current_week_start = current_week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    rolling_data = []
    for week_offset in range(num_weeks - 1, -1, -1):  # Oldest to newest
        week_start = current_week_start - timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        week_time = time_log[(time_log['Date'] >= week_start) & (time_log['Date'] <= week_end)]

        week_data = {
            'week_start': week_start,
            'week_label': week_start.strftime('%m/%d'),
            'total': week_time['Hours'].sum() if len(week_time) > 0 else 0,
            'by_project': {}
        }

        for parent_code, config in PROJECT_CONFIG.items():
            project_time = week_time[week_time['Parent (auto)'] == config['display_name']]
            week_data['by_project'][parent_code] = project_time['Hours'].sum() if len(project_time) > 0 else 0

        rolling_data.append(week_data)

    return rolling_data

def calculate_prev_week_daily(data, week_dates):
    """Calculate daily hours for previous week."""
    time_log = data['time_log']
    prev_start, prev_end = week_dates['previous']

    prev_week_time = time_log[(time_log['Date'] >= prev_start) & (time_log['Date'] <= prev_end)]

    daily_hours = {}
    for i in range(7):
        day_date = prev_start + timedelta(days=i)
        day_name = day_date.strftime('%a')
        day_time = prev_week_time[prev_week_time['Date'].dt.date == day_date.date()]
        daily_hours[day_name] = {
            'date': day_date.strftime('%Y-%m-%d'),
            'total': day_time['Hours'].sum() if len(day_time) > 0 else 0,
            'by_project': {}
        }
        for parent_code, config in PROJECT_CONFIG.items():
            project_time = day_time[day_time['Parent (auto)'] == config['display_name']]
            daily_hours[day_name]['by_project'][parent_code] = project_time['Hours'].sum() if len(project_time) > 0 else 0

    return daily_hours

def get_tasks_by_category(data):
    """Get tasks grouped by parent category with detailed stats."""
    tasks = data['tasks']
    time_log = data['time_log']

    categories = {}
    for parent_code, config in PROJECT_CONFIG.items():
        display_name = config['display_name']
        project_tasks = tasks[tasks['Parent Category'] == display_name].copy()

        if len(project_tasks) == 0:
            continue

        # Get actual hours per task from time log
        task_hours = {}
        for task_id in project_tasks['Task ID'].unique():
            task_time = time_log[time_log['Task ID'] == task_id]
            task_hours[task_id] = task_time['Hours'].sum() if len(task_time) > 0 else 0

        project_tasks['actual_hours'] = project_tasks['Task ID'].map(task_hours)

        categories[parent_code] = {
            'config': config,
            'tasks': project_tasks,
            'stats': {
                'total': len(project_tasks),
                'complete': len(project_tasks[project_tasks['Status'] == 'Complete']),
                'in_progress': len(project_tasks[project_tasks['Status'] == 'In Progress']),
                'planned': len(project_tasks[project_tasks['Status'] == 'Planned']),
                'blocked': len(project_tasks[project_tasks['Status'] == 'Blocked']),
                'total_hours': project_tasks['actual_hours'].sum()
            }
        }

    return categories

# =============================================================================
# HTML GENERATION
# =============================================================================

def generate_css():
    """Return CSS styles for the dashboard."""
    return """
:root {
    --gradient-start: #1a1a2e; --gradient-mid: #16213e; --gradient-end: #0f3460;
    --accent-primary: #4facfe; --accent-secondary: #00f2fe;
    --text-primary: #e8e8e8; --text-secondary: #8892b0;
    --card-bg: rgba(255,255,255,0.05); --card-border: rgba(255,255,255,0.1);
    --success: #00d68f; --warning: #ffaa00; --danger: #ff6b6b;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-mid) 50%, var(--gradient-end) 100%);
    min-height: 100vh; color: var(--text-primary); padding: 40px 20px; line-height: 1.6; }
.container { max-width: 1400px; margin: 0 auto; }
header { text-align: center; margin-bottom: 40px; padding: 30px; background: var(--card-bg);
    border-radius: 20px; border: 1px solid var(--card-border); backdrop-filter: blur(10px); }
h1 { font-size: 2.5rem; background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
.subtitle { color: var(--text-secondary); font-size: 1.1rem; }
.week-range { margin-top: 10px; font-size: 1.3rem; color: var(--accent-primary); font-weight: 600; }
.generated { color: var(--text-secondary); font-size: 0.85rem; margin-top: 5px; }
.quick-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 30px; }
.quick-stat { background: var(--card-bg); border-radius: 12px; padding: 20px; text-align: center;
    border: 1px solid var(--card-border); transition: transform 0.3s; }
.quick-stat:hover { transform: translateY(-3px); box-shadow: 0 8px 30px rgba(79,172,254,0.15); }
.quick-stat-value { font-size: 2rem; font-weight: 700; background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.quick-stat-label { color: var(--text-secondary); font-size: 0.85rem; margin-top: 4px; }
.quick-stat-delta { font-size: 0.75rem; margin-top: 6px; }
.quick-stat-delta.positive { color: var(--success); }
.quick-stat-delta.negative { color: var(--danger); }
section { background: var(--card-bg); border-radius: 16px; padding: 28px; margin-bottom: 24px;
    border: 1px solid var(--card-border); backdrop-filter: blur(10px); }
h2 { font-size: 1.4rem; margin-bottom: 20px; color: var(--accent-primary); }
h3 { font-size: 1.1rem; color: var(--text-primary); margin-bottom: 12px; }
.projects-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
.project-card { background: rgba(255,255,255,0.03); border-radius: 14px; padding: 24px;
    border: 1px solid var(--card-border); transition: all 0.3s ease; }
.project-card:hover { border-color: var(--accent-primary); box-shadow: 0 0 20px rgba(79,172,254,0.1); }
.project-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.project-name { font-size: 1.15rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.project-meta { display: flex; gap: 12px; margin-top: 12px; font-size: 0.85rem; color: var(--text-secondary); }
.project-hours { font-size: 1.8rem; font-weight: 700; color: var(--accent-primary); }
.project-hours-label { font-size: 0.8rem; color: var(--text-secondary); }
.progress-container { margin: 12px 0; }
.progress-header { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.85rem; }
.progress-bar { height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.subcategory-list { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--card-border); }
.subcategory-item { display: flex; justify-content: space-between; padding: 6px 0; font-size: 0.9rem;
    border-bottom: 1px solid rgba(255,255,255,0.03); }
.subcategory-item:last-child { border-bottom: none; }
.subcategory-name { color: var(--text-secondary); }
.subcategory-hours { color: var(--text-primary); font-weight: 500; }
.subcategory-hours.has-hours { color: var(--accent-primary); }
.badge { padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.status-in-progress { background: rgba(79,172,254,0.2); color: #4facfe; }
.status-blocked { background: rgba(255,107,107,0.2); color: #ff6b6b; }
.status-complete { background: rgba(0,214,143,0.2); color: #00d68f; }
.status-planned { background: rgba(136,146,176,0.2); color: #8892b0; }
.scope-added { background: rgba(255,170,0,0.2); color: #ffaa00; }
.scope-reduced { background: rgba(155,89,182,0.2); color: #9b59b6; }
.blockers-section { background: linear-gradient(135deg, rgba(255,107,107,0.1), rgba(255,107,107,0.05));
    border: 1px solid rgba(255,107,107,0.3); }
.blockers-section h2 { color: var(--danger); }
.scope-section { background: linear-gradient(135deg, rgba(255,170,0,0.1), rgba(255,170,0,0.05));
    border: 1px solid rgba(255,170,0,0.3); }
.scope-section h2 { color: var(--warning); }
.task-list { list-style: none; }
.task-list li { padding: 14px 18px; margin-bottom: 10px; background: rgba(255,255,255,0.02); border-radius: 10px;
    display: flex; align-items: flex-start; gap: 14px; border-left: 4px solid transparent; }
.task-list li:hover { background: rgba(255,255,255,0.04); }
.task-list li.blocked { border-left-color: var(--danger); background: rgba(255,107,107,0.05); }
.task-list li.in-progress { border-left-color: var(--accent-primary); }
.task-list li.planned { border-left-color: var(--text-secondary); }
.task-list li.scope-change { border-left-color: var(--warning); background: rgba(255,170,0,0.05); }
.task-icon { font-size: 1.1rem; flex-shrink: 0; }
.task-content { flex: 1; }
.task-id { font-size: 0.75rem; color: var(--accent-primary); font-family: monospace; margin-bottom: 2px; }
.task-title { font-weight: 600; color: var(--text-primary); }
.task-project { font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px; }
.task-badges { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.heatmap-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.heatmap-table th { background: rgba(255,255,255,0.05); padding: 12px 8px; text-align: center;
    border-bottom: 2px solid rgba(255,255,255,0.1); color: var(--accent-primary); font-weight: 600; }
.heatmap-table th:first-child { text-align: left; width: 35%; }
.heatmap-table td { padding: 10px 8px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.05); }
.heatmap-table td:first-child { text-align: left; font-weight: 500; }
.heatmap-table tr:hover { background: rgba(255,255,255,0.02); }
.row-project { font-weight: 600; background: rgba(255,255,255,0.03); }
.row-total { font-weight: 700; background: rgba(79,172,254,0.1); border-top: 2px solid rgba(79,172,254,0.3); }
.heat-0 { background: transparent; color: var(--text-secondary); }
.heat-1 { background: rgba(79,172,254,0.15); }
.heat-2 { background: rgba(79,172,254,0.3); }
.heat-3 { background: rgba(0,242,254,0.3); }
.heat-4 { background: rgba(255,170,0,0.3); }
.heat-5 { background: rgba(255,107,107,0.4); font-weight: 600; }
.week-col { min-width: 70px; background: rgba(79,172,254,0.05); }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
.summary-card { background: rgba(255,255,255,0.03); border-radius: 12px; padding: 20px; border: 1px solid var(--card-border); }
.summary-bar-item { margin-bottom: 12px; }
.summary-bar-label { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px; }
.summary-bar-track { height: 20px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.summary-bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; justify-content: flex-end;
    padding-right: 8px; font-size: 0.75rem; font-weight: 600; color: var(--gradient-start); min-width: 30px; }
.status-item { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
.status-item:last-child { border-bottom: none; }
.status-dot { width: 12px; height: 12px; border-radius: 50%; }
.status-dot.complete { background: var(--success); }
.status-dot.in-progress { background: var(--accent-primary); }
.status-dot.blocked { background: var(--danger); }
.status-dot.backlog { background: var(--text-secondary); }
footer { text-align: center; margin-top: 40px; padding: 20px; color: var(--text-secondary); font-size: 0.9rem; }
@media (max-width: 768px) { .projects-grid { grid-template-columns: 1fr; } h1 { font-size: 1.8rem; } }
@media print { body { background: white; color: #333; } section { border: 1px solid #ddd; background: white; } }
"""

def generate_blockers_section(blocked_tasks):
    """Generate blockers section HTML."""
    if len(blocked_tasks) == 0:
        return ""
    html = '<section class="blockers-section"><h2>🚨 Blockers</h2><ul class="task-list">'
    for _, task in blocked_tasks.iterrows():
        task_id = task.get('Task ID', '')
        title = task.get('Title', 'Untitled')
        parent = task.get('Parent Category', '')
        desc = task.get('Description', '')
        desc_html = f'<div class="task-project">{desc}</div>' if pd.notna(desc) and desc else ''
        html += f'''<li class="blocked"><span class="task-icon">⛔</span>
            <div class="task-content"><div class="task-id">{task_id}</div>
            <div class="task-title">{title}</div><div class="task-project">{parent}</div>{desc_html}</div></li>'''
    html += '</ul></section>'
    return html

def generate_scope_section(scope_tasks):
    """Generate scope changes section HTML."""
    if len(scope_tasks) == 0:
        return ""
    html = '<section class="scope-section"><h2>⚠️ Scope Changes</h2><ul class="task-list">'
    for _, task in scope_tasks.iterrows():
        task_id = task.get('Task ID', '')
        title = task.get('Title', 'Untitled')
        scope_change = task.get('Scope Change', '')
        scope_note = task.get('Scope Note', '')
        icon = "➕" if scope_change == "Added" else "➖"
        badge_class = "scope-added" if scope_change == "Added" else "scope-reduced"
        note_html = f'<div class="task-project">{scope_note}</div>' if pd.notna(scope_note) and scope_note else ''
        html += f'''<li class="scope-change"><span class="task-icon">{icon}</span>
            <div class="task-content"><div class="task-id">{task_id}</div>
            <div class="task-title">{title}</div>
            <div class="task-badges"><span class="badge {badge_class}">{scope_change}</span></div>
            {note_html}</div></li>'''
    html += '</ul></section>'
    return html

def generate_project_cards(data, metrics, subcategory_hours):
    """Generate project cards HTML."""
    html = ""
    for parent_code, config in PROJECT_CONFIG.items():
        hours = metrics['hours_by_project'].get(parent_code, 0)
        task_stats = metrics['tasks_by_project'].get(parent_code, {})
        total_tasks = task_stats.get('total', 0)
        complete_tasks = task_stats.get('complete', 0)
        progress = (complete_tasks / total_tasks * 100) if total_tasks > 0 else 0
        subcats = subcategory_hours.get(parent_code, {})
        all_subcats = get_subcategories_for_project(data, parent_code)

        html += f'''<div class="project-card" style="border-left: 4px solid {config['color']};">
            <div class="project-header"><div>
                <div class="project-name"><span>{config['icon']}</span>{config['display_name']}</div>
                <div class="project-meta">
                    <span>{task_stats.get('in_progress', 0)} in progress</span>
                    <span>{task_stats.get('blocked', 0)} blocked</span>
                    <span>{complete_tasks}/{total_tasks} complete</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div class="project-hours">{hours:.1f}</div>
                <div class="project-hours-label">hrs this week</div>
            </div></div>
            <div class="progress-container">
                <div class="progress-header"><span>Task Completion</span><span>{progress:.0f}%</span></div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {progress}%; background: {config['color']};"></div>
                </div>
            </div>
            <div class="subcategory-list"><strong style="color: var(--text-secondary); font-size: 0.85rem;">Subcategory Hours</strong>'''

        for subcat in all_subcats:
            subcat_hours = subcats.get(subcat, 0)
            hours_class = "has-hours" if subcat_hours > 0 else ""
            html += f'<div class="subcategory-item"><span class="subcategory-name">{subcat}</span><span class="subcategory-hours {hours_class}">{subcat_hours:.1f}</span></div>'
        html += '</div></div>'
    return html

def generate_time_heatmap(metrics):
    """Generate time heatmap table HTML."""
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    html = '<table class="heatmap-table"><thead><tr><th>Project</th>'
    for day in days:
        day_data = metrics['daily_hours'].get(day, {})
        date_str = day_data.get('date', '')
        html += f'<th>{day}<br><small>{date_str}</small></th>'
    html += '<th class="week-col">Week</th></tr></thead><tbody>'

    for parent_code, config in PROJECT_CONFIG.items():
        week_total = metrics['hours_by_project'].get(parent_code, 0)
        html += f'<tr class="row-project"><td>{config["icon"]} {config["display_name"]}</td>'
        for day in days:
            day_data = metrics['daily_hours'].get(day, {})
            day_hours = day_data.get('by_project', {}).get(parent_code, 0)
            heat = get_heat_class(day_hours)
            display = f"{day_hours:.1f}" if day_hours > 0 else "-"
            html += f'<td class="{heat}">{display}</td>'
        html += f'<td class="week-col {get_heat_class(week_total)}">{week_total:.1f}</td></tr>'

    total_week = sum(metrics['hours_by_project'].values())
    html += '<tr class="row-total"><td>📊 TOTAL</td>'
    for day in days:
        day_data = metrics['daily_hours'].get(day, {})
        day_total = day_data.get('total', 0)
        display = f"{day_total:.1f}" if day_total > 0 else "-"
        html += f'<td class="{get_heat_class(day_total)}">{display}</td>'
    html += f'<td class="week-col {get_heat_class(total_week)}">{total_week:.1f}</td></tr></tbody></table>'
    return html

def generate_task_list(tasks):
    """Generate active task list HTML."""
    if len(tasks) == 0:
        return '<p style="color: var(--text-secondary);">No active tasks.</p>'
    html = '<ul class="task-list">'
    for _, task in tasks.iterrows():
        task_id = task.get('Task ID', '')
        title = task.get('Title', 'Untitled')
        parent = task.get('Parent Category', '')
        status = task.get('Status', '')
        priority = task.get('Priority', '')

        status_class = status.lower().replace(' ', '-') if pd.notna(status) else ''
        icon = {'Blocked': '⛔', 'In Progress': '🔄', 'Planned': '📅'}.get(status, '📋')

        priority_class = ''
        if pd.notna(priority):
            if 'Critical' in str(priority): priority_class = 'priority-p1'
            elif 'High' in str(priority): priority_class = 'priority-p2'
            elif 'Medium' in str(priority): priority_class = 'priority-p3'
            else: priority_class = 'priority-p4'

        status_badge_class = f'status-{status_class}' if status_class else 'status-planned'

        html += f'''<li class="{status_class}"><span class="task-icon">{icon}</span>
            <div class="task-content"><div class="task-id">{task_id}</div>
            <div class="task-title">{title}</div><div class="task-project">{parent}</div>
            <div class="task-badges">
                <span class="badge {status_badge_class}">{status}</span>
                <span class="badge {priority_class}">{priority}</span>
            </div></div></li>'''
    html += '</ul>'
    return html

def generate_summary_section(metrics):
    """Generate weekly summary section."""
    total_week = sum(metrics['hours_by_project'].values())
    html = '<div class="summary-grid"><div class="summary-card"><h3>Hours by Project</h3><div>'

    for parent_code, config in PROJECT_CONFIG.items():
        hours = metrics['hours_by_project'].get(parent_code, 0)
        pct = (hours / total_week * 100) if total_week > 0 else 0
        html += f'''<div class="summary-bar-item">
            <div class="summary-bar-label"><span>{config['icon']} {config['display_name']}</span><span>{hours:.1f} hrs</span></div>
            <div class="summary-bar-track">
                <div class="summary-bar-fill" style="width: {pct}%; background: {config['color']};">{pct:.0f}%</div>
            </div></div>'''

    html += '''</div></div><div class="summary-card"><h3>Task Status</h3><div class="task-status-summary">'''
    html += f'''<div class="status-item"><span class="status-dot complete"></span><span>Complete: {metrics['tasks_complete']}</span></div>
        <div class="status-item"><span class="status-dot in-progress"></span><span>In Progress: {metrics['tasks_in_progress']}</span></div>
        <div class="status-item"><span class="status-dot blocked"></span><span>Blocked: {metrics['tasks_blocked']}</span></div>
        <div class="status-item"><span class="status-dot backlog"></span><span>Total Tasks: {metrics['total_tasks']}</span></div>'''
    html += '</div></div></div>'
    return html

def generate_session_logs_section(sessions):
    """Generate recent session logs section."""
    if not sessions:
        return ""
    html = '''<section>
        <h2>📝 Recent Development Sessions</h2>
        <div class="session-logs">'''
    for session in sessions:
        html += f'''<div class="session-card">
            <div class="session-header">
                <span class="session-date">{session['date']}</span>
                <span class="session-focus">{session['focus']}</span>
            </div>
            <div class="session-summary">{session['summary']}</div>
        </div>'''
    html += '</div></section>'
    return html

def generate_time_heatmap_with_prev(metrics, prev_week_daily, week_dates):
    """Generate time heatmap with current and previous week comparison."""
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    prev_start, _ = week_dates['previous']

    html = '''<table class="heatmap-table"><thead><tr><th>Project / Week</th>'''
    for day in days:
        day_data = metrics['daily_hours'].get(day, {})
        date_str = day_data.get('date', '')
        html += f'<th>{day}<br><small>{date_str}</small></th>'
    html += '<th class="week-col">Total</th></tr></thead><tbody>'

    # Current week header
    html += f'<tr style="background: rgba(79,172,254,0.1);"><td colspan="9" style="font-weight: 600; color: var(--accent-primary);">This Week</td></tr>'

    # Current week by project
    for parent_code, config in PROJECT_CONFIG.items():
        week_total = metrics['hours_by_project'].get(parent_code, 0)
        html += f'<tr class="row-project"><td>{config["icon"]} {config["display_name"]}</td>'
        for day in days:
            day_data = metrics['daily_hours'].get(day, {})
            day_hours = day_data.get('by_project', {}).get(parent_code, 0)
            heat = get_heat_class(day_hours)
            display = f"{day_hours:.1f}" if day_hours > 0 else "-"
            html += f'<td class="{heat}">{display}</td>'
        html += f'<td class="week-col {get_heat_class(week_total)}">{week_total:.1f}</td></tr>'

    # Current week total
    total_week = sum(metrics['hours_by_project'].values())
    html += '<tr class="row-total"><td>Current Week Total</td>'
    for day in days:
        day_data = metrics['daily_hours'].get(day, {})
        day_total = day_data.get('total', 0)
        display = f"{day_total:.1f}" if day_total > 0 else "-"
        html += f'<td class="{get_heat_class(day_total)}">{display}</td>'
    html += f'<td class="week-col {get_heat_class(total_week)}">{total_week:.1f}</td></tr>'

    # Previous week header
    html += f'<tr style="background: rgba(136,146,176,0.1);"><td colspan="9" style="font-weight: 600; color: var(--text-secondary);">Last Week ({prev_start.strftime("%m/%d")})</td></tr>'

    # Previous week by project
    prev_totals = {}
    for parent_code, config in PROJECT_CONFIG.items():
        prev_totals[parent_code] = sum(prev_week_daily.get(day, {}).get('by_project', {}).get(parent_code, 0) for day in days)
        html += f'<tr style="opacity: 0.7;"><td>{config["icon"]} {config["display_name"]}</td>'
        for day in days:
            day_data = prev_week_daily.get(day, {})
            day_hours = day_data.get('by_project', {}).get(parent_code, 0)
            heat = get_heat_class(day_hours)
            display = f"{day_hours:.1f}" if day_hours > 0 else "-"
            html += f'<td class="{heat}">{display}</td>'
        html += f'<td class="week-col {get_heat_class(prev_totals[parent_code])}">{prev_totals[parent_code]:.1f}</td></tr>'

    # Previous week total
    prev_total_week = sum(prev_totals.values())
    html += '<tr style="opacity: 0.7; font-weight: 600;"><td>Last Week Total</td>'
    for day in days:
        day_data = prev_week_daily.get(day, {})
        day_total = day_data.get('total', 0)
        display = f"{day_total:.1f}" if day_total > 0 else "-"
        html += f'<td class="{get_heat_class(day_total)}">{display}</td>'
    html += f'<td class="week-col {get_heat_class(prev_total_week)}">{prev_total_week:.1f}</td></tr>'

    html += '</tbody></table>'
    return html

def generate_rolling_chart(rolling_data):
    """Generate SVG line chart for rolling 8-week trends."""
    if not rolling_data:
        return '<p style="color: var(--text-secondary);">No historical data available.</p>'

    # Chart dimensions
    width, height = 800, 300
    padding = 60
    chart_width = width - 2 * padding
    chart_height = height - 2 * padding

    # Find max value for scaling
    max_val = max(week['total'] for week in rolling_data) or 50
    max_val = max(max_val, 50)  # Minimum scale of 50 hours

    # Generate SVG
    html = f'''<div style="overflow-x: auto;">
        <svg viewBox="0 0 {width} {height}" style="width: 100%; max-width: {width}px; height: auto;">
        <!-- Background grid -->
        <defs>
            <linearGradient id="gridGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:rgba(79,172,254,0.1)"/>
                <stop offset="100%" style="stop-color:rgba(79,172,254,0)"/>
            </linearGradient>
        </defs>
        <rect x="{padding}" y="{padding}" width="{chart_width}" height="{chart_height}" fill="url(#gridGradient)" rx="8"/>

        <!-- Grid lines -->'''

    # Y-axis grid lines and labels
    for i in range(5):
        y = padding + (chart_height / 4) * i
        val = max_val - (max_val / 4) * i
        html += f'''
        <line x1="{padding}" y1="{y}" x2="{width - padding}" y2="{y}" stroke="rgba(255,255,255,0.1)" stroke-dasharray="4"/>
        <text x="{padding - 10}" y="{y + 4}" fill="#8892b0" font-size="11" text-anchor="end">{val:.0f}</text>'''

    # X-axis labels
    x_step = chart_width / (len(rolling_data) - 1) if len(rolling_data) > 1 else chart_width
    for i, week in enumerate(rolling_data):
        x = padding + x_step * i
        html += f'''
        <text x="{x}" y="{height - 20}" fill="#8892b0" font-size="11" text-anchor="middle">{week['week_label']}</text>'''

    # Draw lines for each project
    for parent_code, config in PROJECT_CONFIG.items():
        points = []
        for i, week in enumerate(rolling_data):
            x = padding + x_step * i
            val = week['by_project'].get(parent_code, 0)
            y = padding + chart_height - (val / max_val * chart_height)
            points.append(f"{x},{y}")

        if points:
            html += f'''
        <polyline points="{' '.join(points)}" fill="none" stroke="{config['color']}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'''
            # Data points
            for i, week in enumerate(rolling_data):
                x = padding + x_step * i
                val = week['by_project'].get(parent_code, 0)
                y = padding + chart_height - (val / max_val * chart_height)
                html += f'''
        <circle cx="{x}" cy="{y}" r="4" fill="{config['color']}" stroke="var(--gradient-start)" stroke-width="2"/>'''

    # Total line (dashed)
    points = []
    for i, week in enumerate(rolling_data):
        x = padding + x_step * i
        val = week['total']
        y = padding + chart_height - (val / max_val * chart_height)
        points.append(f"{x},{y}")
    html += f'''
        <polyline points="{' '.join(points)}" fill="none" stroke="#e8e8e8" stroke-width="2" stroke-dasharray="6" opacity="0.7"/>'''

    html += '''
        </svg>
    </div>
    <div style="display: flex; gap: 20px; justify-content: center; margin-top: 16px; flex-wrap: wrap;">'''

    # Legend
    for parent_code, config in PROJECT_CONFIG.items():
        html += f'''<div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 3px; background: {config['color']}; border-radius: 2px;"></div>
            <span style="font-size: 0.85rem; color: var(--text-secondary);">{config['display_name']}</span>
        </div>'''
    html += '''<div style="display: flex; align-items: center; gap: 6px;">
        <div style="width: 16px; height: 0; border-top: 2px dashed #e8e8e8;"></div>
        <span style="font-size: 0.85rem; color: var(--text-secondary);">Total</span>
    </div></div>'''

    return html

def generate_gsd_hierarchy_section():
    """Generate GSD-style task hierarchy visualization."""
    html = '''<section>
        <h2>🎯 GSD Task Hierarchy — Synthesize Datasets</h2>
        <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 0.9rem;">
            Task breakdown from Meta GSD (Goals, Signals, Metrics)
        </p>
        <div class="gsd-container">'''

    for project_name, project_data in GSD_TASKS.items():
        html += f'''<div class="gsd-project">
            <div class="gsd-project-header">
                <span>{project_data['icon']}</span> {project_name}
            </div>
            <div class="gsd-sections">'''

        for section_name, section_data in project_data['sections'].items():
            status = section_data['status']
            status_icon = {'complete': '[OK]', 'in_progress': '[...]', 'ongoing': '[~]', 'planned': '[ ]'}.get(status, '[ ]')
            status_class = status.replace('_', '-')

            html += f'''<div class="gsd-section gsd-{status_class}">
                <div class="gsd-section-header">
                    <span class="gsd-status-icon">{status_icon}</span>
                    <span class="gsd-section-name">{section_name}</span>
                    <span class="badge status-{status_class}">{status.replace('_', ' ').title()}</span>
                </div>'''

            if section_data['tasks']:
                html += '<div class="gsd-tasks">'
                for task in section_data['tasks']:
                    task_status = task.get('status', 'planned')
                    task_icon = {'complete': '[OK]', 'in_progress': '[...]', 'planned': '[ ]'}.get(task_status, '[ ]')

                    html += f'''<div class="gsd-task">
                        <span class="gsd-task-icon">{task_icon}</span>
                        <span class="gsd-task-name">{task['name']}</span>
                        <span class="badge status-{task_status.replace('_', '-')}">{task_status.replace('_', ' ')}</span>
                    </div>'''

                    # Subtasks
                    if 'subtasks' in task:
                        html += '<div class="gsd-subtasks">'
                        for subtask in task['subtasks']:
                            st_status = subtask.get('status', 'planned')
                            st_icon = {'complete': '[OK]', 'in_progress': '[...]', 'planned': '[ ]'}.get(st_status, '[ ]')
                            html += f'''<div class="gsd-subtask">
                                <span class="gsd-task-icon">{st_icon}</span>
                                <span class="gsd-task-name">{subtask['name']}</span>
                            </div>'''
                        html += '</div>'

                html += '</div>'

            html += '</div>'

        html += '</div></div>'

    html += '</div></section>'
    return html


def generate_accomplishments_section():
    """Generate accomplishments timeline from past 2 months."""
    html = '''<section>
        <h2>🏆 Key Accomplishments — Past 2 Months</h2>
        <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 0.9rem;">
            Major deliverables extracted from development sessions and documentation
        </p>
        <div class="accomplishments-timeline">'''

    # Group by month
    current_month = None
    for acc in ACCOMPLISHMENTS:
        date_str = acc['date']
        month = date_str.split(',')[0] if ',' in date_str else date_str.split()[0] + ' ' + date_str.split()[1] if len(date_str.split()) > 1 else date_str

        if month != current_month:
            if current_month is not None:
                html += '</div>'  # Close previous month
            html += f'''<div class="accomplishment-month">
                <div class="month-header">{month}</div>'''
            current_month = month

        category_colors = {
            'PM & Documentation': '#9b59b6',
            'SemiAnalysis Integration': '#e74c3c',
            'Pipeline Enhancement': '#3498db',
            'Schema Design': '#2ecc71',
            'Automation': '#f39c12',
            'Report Card': '#1abc9c',
            'Data Integration': '#34495e',
            'Pipeline Architecture': '#16a085',
            'Data Processing': '#27ae60',
            'XB Table': '#2980b9',
            'Project Initiation': '#8e44ad'
        }
        color = category_colors.get(acc['category'], '#4facfe')

        html += f'''<div class="accomplishment-item" style="border-left-color: {color};">
            <div class="accomplishment-header">
                <span class="accomplishment-date">{acc['date']}</span>
                <span class="accomplishment-category" style="background: {color}20; color: {color};">{acc['category']}</span>
            </div>
            <div class="accomplishment-title">{acc['title']}</div>
            <div class="accomplishment-desc">{acc['description']}</div>
        </div>'''

    html += '''</div></div></section>'''
    return html


def generate_tasks_by_category_section(categories):
    """Generate detailed task list by category."""
    if not categories:
        return '<p style="color: var(--text-secondary);">No tasks found.</p>'

    html = '<div class="category-accordion">'
    for parent_code, cat_data in categories.items():
        config = cat_data['config']
        stats = cat_data['stats']
        tasks = cat_data['tasks']

        progress = (stats['complete'] / stats['total'] * 100) if stats['total'] > 0 else 0

        html += f'''<div class="category-section" style="border-left: 4px solid {config['color']}; margin-bottom: 20px; padding: 16px; background: rgba(255,255,255,0.02); border-radius: 0 12px 12px 0;">
            <div class="category-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div>
                    <h3 style="margin: 0; display: flex; align-items: center; gap: 8px;">{config['icon']} {config['display_name']}</h3>
                    <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px;">
                        {stats['complete']}/{stats['total']} tasks complete | {stats['total_hours']:.1f} hrs logged
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.5rem; font-weight: 700; color: {config['color']};">{progress:.0f}%</div>
                </div>
            </div>
            <div class="progress-bar" style="height: 6px; margin-bottom: 12px;">
                <div class="progress-fill" style="width: {progress}%; background: {config['color']};"></div>
            </div>
            <table style="width: 100%; font-size: 0.85rem;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--card-border);">
                        <th style="text-align: left; padding: 8px 4px; color: var(--text-secondary);">Task</th>
                        <th style="text-align: center; padding: 8px 4px; color: var(--text-secondary);">Status</th>
                        <th style="text-align: right; padding: 8px 4px; color: var(--text-secondary);">Hours</th>
                        <th style="text-align: right; padding: 8px 4px; color: var(--text-secondary);">Due</th>
                    </tr>
                </thead>
                <tbody>'''

        for _, task in tasks.iterrows():
            task_id = task.get('Task ID', '')
            title = task.get('Title', 'Untitled')
            status = task.get('Status', '')
            hours = task.get('actual_hours', 0)
            due_date = task.get('Due Date', '')

            status_class = status.lower().replace(' ', '-') if pd.notna(status) else ''
            status_badge = f'<span class="badge status-{status_class}">{status}</span>' if status else '-'
            due_str = pd.to_datetime(due_date).strftime('%m/%d') if pd.notna(due_date) else '-'

            html += f'''<tr style="border-bottom: 1px solid rgba(255,255,255,0.03);">
                <td style="padding: 8px 4px;"><span style="color: var(--accent-primary); font-family: monospace; font-size: 0.75rem;">{task_id}</span> {title[:40]}{'...' if len(str(title)) > 40 else ''}</td>
                <td style="text-align: center; padding: 8px 4px;">{status_badge}</td>
                <td style="text-align: right; padding: 8px 4px; color: {'var(--accent-primary)' if hours > 0 else 'var(--text-secondary)'};">{hours:.1f}</td>
                <td style="text-align: right; padding: 8px 4px; color: var(--text-secondary);">{due_str}</td>
            </tr>'''

        html += '''</tbody></table></div>'''

    html += '</div>'
    return html

# =============================================================================
# MAIN GENERATION
# =============================================================================

def generate_html(data, metrics, week_dates, subcategory_hours, prev_week_daily, rolling_data, sessions, categories):
    """Generate the complete HTML dashboard."""
    current_start, current_end = week_dates['current']
    week_range = f"{current_start.strftime('%B %d')} – {current_end.strftime('%d, %Y')}"

    blocked_tasks = get_blocked_tasks(data)
    scope_changes = get_scope_changes(data)
    active_tasks = get_active_tasks(data, limit=15)

    delta_hours = metrics['current_week_hours'] - metrics['prev_week_hours']
    delta_class = "positive" if delta_hours >= 0 else "negative"
    delta_arrow = "+" if delta_hours >= 0 else ""

    # Add session log CSS and new section styles
    session_css = """
.session-logs { display: flex; flex-direction: column; gap: 12px; }
.session-card { background: rgba(255,255,255,0.03); border-radius: 10px; padding: 16px; border-left: 3px solid var(--accent-primary); }
.session-header { display: flex; justify-content: space-between; margin-bottom: 8px; flex-wrap: wrap; gap: 8px; }
.session-date { color: var(--accent-primary); font-weight: 600; font-size: 0.9rem; }
.session-focus { color: var(--text-secondary); font-size: 0.85rem; background: rgba(79,172,254,0.1); padding: 2px 10px; border-radius: 12px; }
.session-summary { color: var(--text-secondary); font-size: 0.9rem; line-height: 1.5; }

/* GSD Hierarchy Styles */
.gsd-container { display: flex; flex-direction: column; gap: 16px; }
.gsd-project { background: rgba(255,255,255,0.02); border-radius: 12px; padding: 20px; }
.gsd-project-header { font-size: 1.2rem; font-weight: 600; color: var(--accent-primary); margin-bottom: 16px; display: flex; align-items: center; gap: 10px; }
.gsd-sections { display: flex; flex-direction: column; gap: 8px; }
.gsd-section { padding: 12px 16px; border-radius: 8px; background: rgba(255,255,255,0.02); border-left: 3px solid var(--text-secondary); }
.gsd-section.gsd-complete { border-left-color: var(--success); }
.gsd-section.gsd-in-progress { border-left-color: var(--accent-primary); }
.gsd-section.gsd-ongoing { border-left-color: var(--warning); }
.gsd-section.gsd-planned { border-left-color: var(--text-secondary); }
.gsd-section-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.gsd-status-icon { font-family: monospace; color: var(--text-secondary); font-size: 0.85rem; }
.gsd-section-name { font-weight: 600; color: var(--text-primary); flex: 1; }
.gsd-tasks { margin-top: 12px; margin-left: 24px; display: flex; flex-direction: column; gap: 8px; }
.gsd-task { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: rgba(255,255,255,0.02); border-radius: 6px; }
.gsd-task-icon { font-family: monospace; color: var(--text-secondary); font-size: 0.8rem; }
.gsd-task-name { flex: 1; color: var(--text-primary); font-size: 0.9rem; }
.gsd-subtasks { margin-left: 28px; margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.gsd-subtask { display: flex; align-items: center; gap: 8px; padding: 6px 10px; font-size: 0.85rem; color: var(--text-secondary); }

/* Accomplishments Timeline Styles */
.accomplishments-timeline { display: flex; flex-direction: column; gap: 0; }
.accomplishment-month { margin-bottom: 4px; }
.month-header { font-size: 1.1rem; font-weight: 700; color: var(--accent-primary); padding: 12px 0 8px 0; border-bottom: 2px solid rgba(79,172,254,0.3); margin-bottom: 12px; }
.accomplishment-item { border-left: 4px solid var(--accent-primary); padding: 12px 16px; margin-left: 8px; margin-bottom: 12px; background: rgba(255,255,255,0.02); border-radius: 0 8px 8px 0; }
.accomplishment-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 8px; }
.accomplishment-date { font-size: 0.8rem; color: var(--text-secondary); }
.accomplishment-category { font-size: 0.75rem; padding: 3px 10px; border-radius: 12px; font-weight: 500; }
.accomplishment-title { font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.accomplishment-desc { font-size: 0.9rem; color: var(--text-secondary); line-height: 1.5; }
"""

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PM Dashboard — Patrick Anderson</title>
    <style>{generate_css()}{session_css}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Project Management Dashboard</h1>
            <p class="subtitle">Patrick Anderson — Infrastructure Intelligence / Geospatial Analytics</p>
            <p class="week-range">Week of {week_range}</p>
            <p class="generated">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </header>

        <div class="quick-stats">
            <div class="quick-stat">
                <div class="quick-stat-value">{metrics['current_week_hours']:.1f}</div>
                <div class="quick-stat-label">Hours This Week</div>
                <div class="quick-stat-delta {delta_class}">{delta_arrow}{delta_hours:.1f} vs last week</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value">{metrics['tasks_in_progress']}</div>
                <div class="quick-stat-label">Tasks In Progress</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value">{len(blocked_tasks)}</div>
                <div class="quick-stat-label">Blockers</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value">{len(scope_changes)}</div>
                <div class="quick-stat-label">Scope Changes</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value">{metrics['total_hours_logged']:.0f}</div>
                <div class="quick-stat-label">Total Hours (All Time)</div>
            </div>
        </div>

        {generate_blockers_section(blocked_tasks)}
        {generate_scope_section(scope_changes)}

        {generate_session_logs_section(sessions)}

        {generate_accomplishments_section()}

        {generate_gsd_hierarchy_section()}

        <section>
            <h2>📁 Project Status</h2>
            <div class="projects-grid">
                {generate_project_cards(data, metrics, subcategory_hours)}
            </div>
        </section>

        <section>
            <h2>⏱️ Time Allocation — Current vs Last Week</h2>
            {generate_time_heatmap_with_prev(metrics, prev_week_daily, week_dates)}
        </section>

        <section>
            <h2>📈 Rolling 8-Week Trend</h2>
            <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 0.9rem;">Hours by project over the last 8 weeks</p>
            {generate_rolling_chart(rolling_data)}
        </section>

        <section>
            <h2>📋 Tasks by Category</h2>
            {generate_tasks_by_category_section(categories)}
        </section>

        <section>
            <h2>📊 Weekly Summary</h2>
            {generate_summary_section(metrics)}
        </section>

        <footer>
            <p>Infrastructure Intelligence — Geospatial Analytics</p>
            <p>Data source: Patrick_Work_Organizer_Hierarchy.xlsx</p>
        </footer>
    </div>
</body>
</html>'''

    return html


def main():
    """Main function to generate the PM Dashboard."""
    print("=" * 60)
    print("PM DASHBOARD GENERATOR")
    print("=" * 60)

    # Load data
    print("\n[1/6] Loading Excel data...")
    data = load_excel_data()
    print(f"      [OK] Tasks: {len(data['tasks'])} records")
    print(f"      [OK] Time Log: {len(data['time_log'])} entries")

    # Load session logs
    print("\n[2/6] Loading session logs...")
    sessions = load_session_logs(limit=3)
    print(f"      [OK] Session logs: {len(sessions)} recent sessions")

    # Calculate dates and metrics
    print("\n[3/6] Calculating metrics...")
    week_dates = calculate_week_dates()
    metrics = calculate_metrics(data, week_dates)
    subcategory_hours = calculate_subcategory_hours(data, week_dates)
    prev_week_daily = calculate_prev_week_daily(data, week_dates)
    rolling_data = calculate_rolling_weeks(data, ROLLING_WEEKS)
    categories = get_tasks_by_category(data)

    current_start, current_end = week_dates['current']
    print(f"      [OK] Current week: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
    print(f"      [OK] Hours this week: {metrics['current_week_hours']:.1f}")
    print(f"      [OK] Hours last week: {metrics['prev_week_hours']:.1f}")
    print(f"      [OK] Rolling weeks: {len(rolling_data)}")
    print(f"      [OK] Categories: {len(categories)}")

    # Generate HTML
    print("\n[4/6] Generating HTML...")
    html_content = generate_html(data, metrics, week_dates, subcategory_hours, prev_week_daily, rolling_data, sessions, categories)

    # Save to main output
    print("\n[5/6] Saving dashboard...")
    output_file = OUTPUT_DIR / "PM_DASHBOARD.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"      [OK] Saved: {output_file}")

    # Save to archive
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_file = ARCHIVE_DIR / f"PM_DASHBOARD_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    with open(archive_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"      [OK] Archived: {archive_file}")

    # Copy to Google Drive if available
    print("\n[6/6] Syncing to Google Drive...")
    if GDRIVE_OUTPUT.exists():
        gdrive_file = GDRIVE_OUTPUT / "PM_DASHBOARD.html"
        with open(gdrive_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"      [OK] Synced: {gdrive_file}")
    else:
        print(f"      [WARN] Google Drive path not found: {GDRIVE_OUTPUT}")

    print("\n" + "=" * 60)
    print("DASHBOARD GENERATION COMPLETE")
    print("=" * 60)

    # Summary
    print(f"\nSummary for week of {current_start.strftime('%B %d, %Y')}:")
    print(f"  - Total hours: {metrics['current_week_hours']:.1f}")
    print(f"  - Tasks in progress: {metrics['tasks_in_progress']}")
    print(f"  - Blocked: {metrics['tasks_blocked']}")
    print(f"  - Scope changes: {metrics['scope_changes']}")
    print(f"  - Session logs: {len(sessions)}")
    print(f"  - 8-week trend data points: {len(rolling_data)}")

    return output_file


if __name__ == "__main__":
    main()
