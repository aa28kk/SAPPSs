import json

import openai
import os

# Load your key from an environment variable
openai.api_key = os.getenv("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")
def get_shooting_advice(performance_data):
    response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[{"role": "user", "content": f"Analyze these shooting scores: {performance_data}"}]
    )
    return response.choices[0].message.content

from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from pathlib import Path

# ============================================================================
# SHOOTING PERFORMANCE ANALYZER WITH API INTEGRATION
# ============================================================================

class ShootingPerformanceAPI:
    """API for analyzing shooting performance and providing recommendations

    This class can optionally call an external feedback API using `FeedbackClient`.
    Provide either a `feedback_client` instance or pass `api_key` and
    `feedback_endpoint` to enable external personalized feedback.
    """

    def __init__(self, feedback_client=None, api_key=None, feedback_endpoint=None):
        self.analysis_history = []

        # wire feedback client: priority: explicit client -> api_key+endpoint -> env vars
        if feedback_client is not None:
            self.feedback_client = feedback_client
        else:
            # lazy import to avoid hard dependency if not used
            try:
                from feedback_client import FeedbackClient
            except Exception:
                FeedbackClient = None

            env_key = None
            env_endpoint = None
            try:
                import os
                env_key = os.getenv('SHOOTING_FEEDBACK_API_KEY')
                env_endpoint = os.getenv('SHOOTING_FEEDBACK_API_ENDPOINT')
            except Exception:
                pass

            if api_key and feedback_endpoint and FeedbackClient:
                self.feedback_client = FeedbackClient(api_key=api_key, endpoint=feedback_endpoint)
            elif env_key and env_endpoint and FeedbackClient:
                self.feedback_client = FeedbackClient(api_key=env_key, endpoint=env_endpoint)
            else:
                self.feedback_client = None
    
    def analyze_session(self, session_data):
        """
        Analyze a session which may contain multiple series.

        Session_data may either be a flat single-series dict (backwards compatible)
        with keys `eights`, `nines`, `tens` (and optional `seven_or_less`) or a dict
        containing `series`: a list of series dicts with keys `seven_or_less`, `eights`, `nines`, `tens`.
        """
        try:
            norm = _normalize_session(session_data)
        except ValueError as ve:
            return {'error': str(ve)}

        total_shots = norm['total_shots']
        score = norm['average_score']

        # Identify weak areas based on aggregated totals per series
        weak_areas = []
        series_count = total_shots // 10
        avg_sevens = norm['total_sevens'] / series_count
        avg_eights = norm['total_eights'] / series_count
        avg_nines = norm['total_nines'] / series_count
        avg_tens = norm['total_tens'] / series_count

        if avg_sevens > 1.5:
            weak_areas.append("Too many low-value shots (7 or less) - focus on basics, don't look as the target, squeeze the trigger smoothly, follow through")
        if avg_eights > 3:
            weak_areas.append('Too many 8s - focus on consistency and trigger control')
        if avg_nines > 6:
            weak_areas.append('Many 9s - refine sight picture- full focus on front sight and visualization to convert 9s to 10s')
        if avg_tens < 3:
            weak_areas.append('Few 10s - practice focusing on the sights and letting the shots break on it won rather than forcing the shots')

        analysis = {
            'date': session_data.get('date', datetime.date),
            'series_count': series_count,
            'total_shots': total_shots,
            'average_score': round(score, 2),
            'score_percentage': round((score / 10) * 100, 2),
            'distribution': {
                '7s_or_less': norm['total_sevens'],
                '8s': norm['total_eights'],
                '9s': norm['total_nines'],
                '10s': norm['total_tens']
            },
            'weak_areas': weak_areas,
            'session_quality': self._rate_session(score),
            'series': norm['series'],
            'series_scores_100': norm.get('series_scores_100', []),
            'session_total_100': norm.get('session_total_100', 0),
            'session_average_100': norm.get('session_average_100', 0)
        }
        
        # If a feedback client is configured, request personalized feedback
        if getattr(self, 'feedback_client', None):
            try:
                fb = self.feedback_client.get_personalized_feedback(session_data, self.analysis_history)
                analysis['personalized_feedback'] = fb
            except Exception as e:
                analysis['personalized_feedback'] = {'error': str(e)}

        self.analysis_history.append(analysis)
        return analysis
    
    def _rate_session(self, score):
        """Rate session quality based on average score"""
        if score >= 9.5:
            return 'Excellent, focus on repeating the same process'
        elif score >= 9.0:
            return 'Very Good, visualization is required to convert close 9s to 10s'
        elif score >= 8.5:
            return 'Good, but focus on the weaker aspects'
        elif score >= 8.0:
            return 'Fair, focus on the basics'
        else:
            return 'Needs Improvement, focus on the basics'
    
    def get_trend_analysis(self, sessions):
        """Analyze trends across multiple sessions"""
        if not sessions:
            return {'error': 'No sessions to analyze'}
        
        scores = [s['average_score'] for s in sessions]
        avg_score = np.mean(scores)
        trend = 'Improving' if scores[-1] > scores[0] else 'Declining' if scores[-1] < scores[0] else 'Stable'
        
        return {
            'total_sessions': len(sessions),
            'average_score': round(avg_score, 2),
            'best_score': max(scores),
            'worst_score': min(scores),
            'trend': trend,
            'scores': scores
        }
    
    def generate_recommendations(self, analysis_list):
        """Generate personalized recommendations based on analysis"""
        if not analysis_list:
            return []
        
        recommendations = []
        
        # Analyze weak areas
        weak_area_count = {}
        total_8s = sum(a['distribution']['8s'] for a in analysis_list)
        total_9s = sum(a['distribution']['9s'] for a in analysis_list)
        total_10s = sum(a['distribution']['10s'] for a in analysis_list)
        
        sessions_count = len(analysis_list)
        
        if total_8s / sessions_count > 2.5:
            recommendations.append({
                'priority': 'High',
                'focus': 'Consistency',
                'action': 'Practice trigger control exercises',
                'duration': '20 minutes daily'
            })
        
        if total_9s / sessions_count > 5:
            recommendations.append({
                'priority': 'High',
                'focus': 'Precision',
                'action': 'Work on sight alignment and sight picture',
                'duration': '15 minutes daily'
            })
        
        if total_10s / sessions_count < 3:
            recommendations.append({
                'priority': 'Medium',
                'focus': 'Accuracy',
                'action': 'Increase dry fire practice with focus on accuracy',
                'duration': '10 minutes daily'
            })
        
        recommendations.append({
            'priority': 'Medium',
            'focus': 'Overall Performance',
            'action': 'Practice in varied environmental conditions',
            'duration': '2-3 sessions per week'
        })
        
        return recommendations


class ShootingDataManager:
    """Manages shooting session data storage and retrieval"""
    
    def __init__(self, data_file='shooting_data.json'):
        self.data_file = data_file
        self.sessions = self._load_data()
    
    def _load_data(self):
        """Load existing data from file"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_data(self):
        """Save data to file"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.sessions, f, indent=2, ensure_ascii=False)
    
    def add_session(self, eights=None, nines=None, tens=None, series=None):
        """Add a new shooting session.

        Accepts either single-series via `eights`, `nines`, `tens` or a `series`
        list where each series is a dict with keys `seven_or_less`, `eights`, `nines`, `tens`.
        """
        if series is None:
            if eights is None or nines is None or tens is None:
                print("Error: provide either series list or eights/nines/tens")
                return False
            if eights + nines + tens != 10:
                print("Error: Total shots must equal 10 for the single series")
                return False
            series = [{
                'seven_or_less': 0,
                'eights': int(eights),
                'nines': int(nines),
                'tens': int(tens)
            }]

        # validate series
        for s in series:
            sevens = int(s.get('seven_or_less', 0))
            eights = int(s.get('eights', 0))
            nines = int(s.get('nines', 0))
            tens = int(s.get('tens', 0))
            if sevens + eights + nines + tens != 10:
                print("Error: Each series must total 10 shots")
                return False

        session = {
            'series': series,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        self.sessions.append(session)
        self._save_data()
        return session
    
    def get_all_sessions(self):
        """Get all sessions"""
        return self.sessions
    
    def get_recent_sessions(self, count=10):
        """Get recent sessions"""
        return self.sessions[-count:]


class PerformanceVisualizer:
    """Create visualizations for shooting performance"""
    
    @staticmethod
    def plot_score_trends(sessions, save_path='score_trends.png'):
        """Plot score trends over time"""
        if not sessions:
            print("No sessions to plot")
            return
        dates = []
        scores = []
        for s in sessions:
            try:
                norm = _normalize_session(s)
            except Exception:
                continue
            dates.append(datetime.strptime(s.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S'))
            # use session average out of 100 for trends
            scores.append(norm.get('session_average_100', norm['average_score'] * 10))
        
        plt.figure(figsize=(12, 6))
        plt.plot(dates, scores, marker='o', linestyle='-', linewidth=2, markersize=8)
        plt.axhline(y=9, color='g', linestyle='--', label='Excellent (9.0+)', alpha=0.7)
        plt.axhline(y=8.5, color='y', linestyle='--', label='Good (8.5+)', alpha=0.7)
        plt.axhline(y=8, color='r', linestyle='--', label='Fair (8.0+)', alpha=0.7)
        
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Average Score (out of 100)', fontsize=12)
        plt.title('Pistol Shooting Performance Trends (avg per series, out of 100)', fontsize=14, fontweight='bold')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        print(f"Score trends chart saved to {save_path}")
        plt.close()
    
    @staticmethod
    def plot_shot_distribution(sessions, save_path='shot_distribution.png'):
        """Plot distribution of 8s, 9s, and 10s"""
        if not sessions:
            print("No sessions to plot")
            return
        eights = []
        nines = []
        tens = []
        sevens = []
        dates = []
        for s in sessions:
            try:
                norm = _normalize_session(s)
            except Exception:
                continue
            sevens.append(norm['total_sevens'])
            eights.append(norm['total_eights'])
            nines.append(norm['total_nines'])
            tens.append(norm['total_tens'])
            dates.append(datetime.strptime(s.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S'))
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x = np.arange(len(dates))
        width = 0.25
        
        ax.bar(x - 1.5*width, sevens, width, label="7s or less (should-have/cancelled)", color='#a2a2a2')
        ax.bar(x - width/2, eights, width, label='8s (Bad)', color='#ff6b6b')
        ax.bar(x + width/2, nines, width, label='9s (Good)', color='#ffd93d')
        ax.bar(x + 1.5*width, tens, width, label='10s (Perfect)', color='#6bcf7f')
        
        ax.set_xlabel('Session Date', fontsize=12)
        ax.set_ylabel('Number of Shots', fontsize=12)
        ax.set_title('Shot Distribution Across Sessions', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([d.strftime('%m-%d') for d in dates], rotation=45)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        print(f"Shot distribution chart saved to {save_path}")
        plt.close()

    @staticmethod
    def plot_session_totals(sessions, save_path='session_totals.png'):
        """Plot total session scores (sum of series, out of series_count*100) and percentage"""
        if not sessions:
            print("No sessions to plot")
            return

        dates = []
        totals = []
        percentages = []
        max_totals = []
        for s in sessions:
            try:
                norm = _normalize_session(s)
            except Exception:
                continue
            dates.append(datetime.strptime(s.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S'))
            totals.append(norm.get('session_total_100', 0))
            max_totals.append(len(norm['series']) * 100)
            percentages.append((norm.get('session_total_100', 0) / (len(norm['series']) * 100)) * 100)

        plt.figure(figsize=(12, 6))
        x = np.arange(len(dates))
        plt.bar(x, totals, color='#4c72b0', label='Session total (sum of series, out of N*100)')
        plt.plot(x, percentages, color='#dd8452', marker='o', label='Session % (of max)')
        plt.xticks(x, [d.strftime('%m-%d') for d in dates], rotation=45)
        plt.xlabel('Date')
        plt.ylabel('Total / Percentage')
        plt.title('Session Totals and Percentages')
        plt.legend()
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        print(f"Session totals chart saved to {save_path}")
        plt.close()
    
    @staticmethod
    def plot_performance_pie(latest_session, save_path='performance_pie.png'):
        """Plot pie chart of latest session"""
        if not latest_session:
            print("No session data available")
            return
        try:
            norm = _normalize_session(latest_session)
        except Exception:
            print("Invalid session format for pie chart")
            return

        sizes = [norm['total_sevens'], norm['total_eights'], norm['total_nines'], norm['total_tens']]
        labels = [f"7s or less\n{norm['total_sevens']}", f"8s (Bad)\n{norm['total_eights']}", 
                  f"9s (Good)\n{norm['total_nines']}", f"10s (Perfect)\n{norm['total_tens']}"]
        colors = ['#a2a2a2', '#ff6b6b', '#ffd93d', '#6bcf7f']
        colors = ['#ff6b6b', '#ffd93d', '#6bcf7f']
        
        plt.figure(figsize=(8, 8))
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.title('Latest Session Shot Distribution', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        print(f"Performance pie chart saved to {save_path}")
        plt.close()


class PracticeScheduleGenerator:
    """Generate personalized practice schedules"""
    
    @staticmethod
    def generate_schedule(recommendations, days=7, save_path='practice_schedule.txt'):
        """Generate a weekly practice schedule"""
        schedule_text = []
        schedule_text.append("=" * 70)
        schedule_text.append("PERSONALIZED PRACTICE SCHEDULE".center(70))
        schedule_text.append("=" * 70)
        schedule_text.append(f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        schedule_text.append(f"Schedule Duration: {days} days\n")
        
        # Group recommendations by priority
        high_priority = [r for r in recommendations if r['priority'] == 'High']
        medium_priority = [r for r in recommendations if r['priority'] == 'Medium']
        
        current_date = datetime.now()
        
        for day in range(days):
            schedule_date = current_date + timedelta(days=day)
            day_name = schedule_date.strftime('%A, %B %d, %Y')
            
            schedule_text.append(f"\n{'─' * 70}")
            schedule_text.append(f"DAY {day + 1}: {day_name}")
            schedule_text.append(f"{'─' * 70}")
            
            # Rotate through exercises
            session_num = day % 3
            
            if session_num == 0:
                schedule_text.append("\n📍 SESSION TYPE: Diagnostic Session")
                schedule_text.append("   - Warm-up: 10 min (loose shooting)")
                schedule_text.append("   - Main: 30 min (record 3 series of 10 shots)")
                schedule_text.append("   - Cool-down: 5 min (review performance)")
                
                for rec in high_priority:
                    schedule_text.append(f"\n🎯 FOCUS: {rec['focus']}")
                    schedule_text.append(f"   Exercise: {rec['action']}")
                    schedule_text.append(f"   Duration: {rec['duration']}")
            
            elif session_num == 1:
                schedule_text.append("\n📍 SESSION TYPE: Technique Development")
                schedule_text.append("   - Warm-up: 5 min (dry fire)")
                schedule_text.append("   - Main: 40 min (technique drills)")
                schedule_text.append("   - Practice: 15 min (live fire)")
                
                if medium_priority:
                    for rec in medium_priority[:2]:
                        schedule_text.append(f"\n🎯 FOCUS: {rec['focus']}")
                        schedule_text.append(f"   Exercise: {rec['action']}")
            
            else:
                schedule_text.append("\n📍 SESSION TYPE: Performance Validation")
                schedule_text.append("   - Warm-up: 5 min")
                schedule_text.append("   - Main: 30 min (2 series of 10 shots)")
                schedule_text.append("   - Analysis: 15 min (track improvements)")
                
                schedule_text.append("\n   Rest and recovery are essential!")
        
        # Add summary section
        schedule_text.append(f"\n\n{'=' * 70}")
        schedule_text.append("IMPLEMENTATION TIPS".center(70))
        schedule_text.append("=" * 70)
        schedule_text.append("\n1. Maintain consistent practice times each day")
        schedule_text.append("2. Track all shots in a notebook or app")
        schedule_text.append("3. Review results weekly to monitor progress")
        schedule_text.append("4. Adjust schedule based on performance trends")
        schedule_text.append("5. Ensure proper rest between sessions (24+ hours)")
        schedule_text.append("6. Consider environmental factors (weather, noise, etc.)")
        schedule_text.append("7. Practice with proper stance, grip, and sight alignment")
        
        schedule_content = "\n".join(schedule_text)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(schedule_content)
        
        print(f"Practice schedule saved to {save_path}")
        return schedule_content


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def print_menu():
    """Display main menu"""
    print("\n" + "=" * 60)
    print("PISTOL SHOOTING PERFORMANCE ANALYZER".center(60))
    print("=" * 60)
    print("\n1. Add New Shooting Session")
    print("2. View Session Statistics")
    print("3. Generate Performance Analysis Report")
    print("4. View Recommendations")
    print("5. Generate Practice Schedule")
    print("6. Create Performance Visualizations")
    print("7. View All Sessions")
    print("8. Exit")
    print("\n" + "=" * 60)


def _normalize_session(session):
    """Normalize a session record (support old flat format and new multi-series).

    Returns a dict with aggregated totals and series list, or raises ValueError on invalid data.
    """
    # Determine series list
    if isinstance(session, dict) and 'series' in session:
        series_list = session['series']
    elif isinstance(session, dict) and all(k in session for k in ('eights', 'nines', 'tens')):
        # backward compatible single-series
        series_list = [{
            'seven_or_less': session.get('seven_or_less', 0),
            'eights': session.get('eights', 0),
            'nines': session.get('nines', 0),
            'tens': session.get('tens', 0)
        }]
    else:
        raise ValueError('Invalid session format')

    total_sevens = total_eights = total_nines = total_tens = 0
    series_scores = []
    for s in series_list:
        sevens = int(s.get('seven_or_less', 0))
        eights = int(s.get('eights', 0))
        nines = int(s.get('nines', 0))
        tens = int(s.get('tens', 0))
        if sevens + eights + nines + tens != 10:
            raise ValueError('Each series must total 10 shots')
        total_sevens += sevens
        total_eights += eights
        total_nines += nines
        total_tens += tens
        # compute per-series average (out of 10) and convert to out-of-100 score
        series_points = sevens * 7 + eights * 8 + nines * 9 + tens * 10
        series_avg = series_points / 10.0
        series_score_100 = round(series_avg * 10, 2)
        series_scores.append(series_score_100)

    total_shots = (len(series_list) * 10)
    # Use value 7 for '7 or less' category when computing scores
    total_score_points = total_sevens * 7 + total_eights * 8 + total_nines * 9 + total_tens * 10
    average_score = total_score_points / total_shots
    # compute out-of-100 metrics
    session_total_100 = round(sum(series_scores), 2)
    session_average_100 = round((session_total_100 / len(series_list)) if series_list else 0, 2)

    return {
        'series': series_list,
        'total_shots': total_shots,
        'total_sevens': total_sevens,
        'total_eights': total_eights,
        'total_nines': total_nines,
        'total_tens': total_tens,
        'average_score': round(average_score, 2),
        'series_scores_100': series_scores,
        'session_total_100': session_total_100,
        'session_average_100': session_average_100
    }


def add_session(data_manager, api):
    """Add a new shooting session"""
    print("\n📝 ADD NEW SHOOTING SESSION")
    print("-" * 40)

    try:
        # Ask user how many series they want to add (a session is a group of series)
        series_list = []
        count_str = input("How many series in this session? (press Enter to add interactively): ").strip()
        if count_str.isdigit() and int(count_str) > 0:
            series_count = int(count_str)
            for i in range(series_count):
                print(f"\nSeries {i+1} of {series_count}:")
                seven = int(input("  Number of '7 or less' shots (should-have/cancelled): "))
                eight = int(input("  Number of 8s (bad shots): "))
                nine = int(input("  Number of 9s (good shots): "))
                ten = int(input("  Number of 10s (perfect shots): "))
                if seven + eight + nine + ten != 10:
                    print(f"  ❌ Error: Series must total 10 shots (you entered {seven+eight+nine+ten}). Aborting session entry.")
                    return
                series_list.append({'seven_or_less': seven, 'eights': eight, 'nines': nine, 'tens': ten})
        else:
            # interactive add until user says done
            idx = 0
            while True:
                idx += 1
                print(f"\nSeries {idx} (enter counts, or just press Enter to finish):")
                seven_in = input("  Number of '7 or less' shots (leave blank to finish): ").strip()
                if seven_in == "":
                    if idx == 1:
                        print("No series entered. Aborting.")
                        return
                    break
                try:
                    seven = int(seven_in)
                    eight = int(input("  Number of 8s (bad shots): "))
                    nine = int(input("  Number of 9s (good shots): "))
                    ten = int(input("  Number of 10s (perfect shots): "))
                except ValueError:
                    print("  ❌ Invalid input. Please enter integer counts.")
                    return
                if seven + eight + nine + ten != 10:
                    print(f"  ❌ Error: Series must total 10 shots (you entered {seven+eight+nine+ten}). Aborting session entry.")
                    return
                series_list.append({'seven_or_less': seven, 'eights': eight, 'nines': nine, 'tens': ten})

        session = data_manager.add_session(series=series_list)
        analysis = api.analyze_session(session)

        print("\n✅ Session Added Successfully!")
        print(f"\nSeries Count: {analysis.get('series_count', 1)}")
        print(f"Score: {analysis['average_score']}/10 ({analysis['score_percentage']}%)")
        print(f"Quality: {analysis['session_quality']}")

        if analysis['weak_areas']:
            print("\nAreas for Improvement:")
            for area in analysis['weak_areas']:
                print(f"  • {area}")

        # Print any personalized feedback from external API
        pf = analysis.get('personalized_feedback')
        if pf:
            print("\nPersonalized Feedback:")
            print(pf)

    except ValueError:
        print("❌ Invalid input. Please enter valid numbers.")


def view_statistics(data_manager, api):
    """View session statistics"""
    sessions = data_manager.get_all_sessions()
    
    if not sessions:
        print("\n❌ No sessions found. Add a session first.")
        return
    
    print("\n📊 SESSION STATISTICS")
    print("-" * 60)
    
    analyses = [api.analyze_session(s) for s in sessions]
    trend = api.get_trend_analysis(analyses)
    
    print(f"Total Sessions: {trend['total_sessions']}")
    print(f"Average Score: {trend['average_score']}/10")
    print(f"Best Score: {trend['best_score']}/10")
    print(f"Worst Score: {trend['worst_score']}/10")
    print(f"Trend: {trend['trend']} →")
    
    # Calculate recent improvement
    if len(analyses) >= 2:
        recent_improvement = analyses[-1]['average_score'] - analyses[0]['average_score']
        direction = "📈" if recent_improvement > 0 else "📉"
        print(f"Overall Improvement: {direction} {abs(recent_improvement):.2f} points")


def generate_report(data_manager, api):
    """Generate detailed analysis report"""
    sessions = data_manager.get_all_sessions()
    
    if not sessions:
        print("\n❌ No sessions found. Add sessions first.")
        return
    
    analyses = [api.analyze_session(s) for s in sessions]
    trend = api.get_trend_analysis(analyses)
    
    print("\n📋 PERFORMANCE ANALYSIS REPORT")
    print("=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Analysis Period: {len(sessions)} sessions")
    print("=" * 60)
    
    print(f"\n🎯 OVERALL STATISTICS:")
    print(f"   Average Score: {trend['average_score']}/10")
    print(f"   Best Score: {trend['best_score']}/10")
    print(f"   Worst Score: {trend['worst_score']}/10")
    print(f"   Performance Trend: {trend['trend']}")
    
    print(f"\n📊 RECENT SESSIONS (Last 5):")
    for i, analysis in enumerate(analyses[-5:], 1):
        date = analysis['date']
        print(f"\n   Session {i} - {date}")
        print(f"   Score: {analysis['average_score']}/10 ({analysis['score_percentage']}%)")
        print(f"   Shot Breakdown: {analysis['distribution']['8s']}×8 + {analysis['distribution']['9s']}×9 + {analysis['distribution']['10s']}×10")


def view_recommendations(data_manager, api):
    """View personalized recommendations"""
    sessions = data_manager.get_all_sessions()
    
    if not sessions:
        print("\n❌ No sessions found. Add sessions first.")
        return
    
    analyses = [api.analyze_session(s) for s in sessions]
    recommendations = api.generate_recommendations(analyses)
    
    print("\n💡 PERSONALIZED RECOMMENDATIONS")
    print("=" * 60)
    
    for i, rec in enumerate(recommendations, 1):
        priority_emoji = "🔴" if rec['priority'] == 'High' else "🟡"
        print(f"\n{priority_emoji} Recommendation {i} ({rec['priority']} Priority)")
        print(f"   Focus: {rec['focus']}")
        print(f"   Action: {rec['action']}")
        print(f"   Duration: {rec['duration']}")


def view_all_sessions(data_manager):
    """View all sessions"""
    sessions = data_manager.get_all_sessions()
    
    if not sessions:
        print("\n❌ No sessions found.")
        return
    
    print("\n📅 ALL SHOOTING SESSIONS")
    print("=" * 95)
    print(f"{'Date':<20} | {'Series':<6} | {'7s<=':<4} | {'8s':<3} | {'9s':<3} | {'10s':<4} | {'Total(pts)':<10} | {'Avg(100)':<8}")
    print("-" * 95)
    
    for session in sessions:
        try:
            norm = _normalize_session(session)
        except Exception:
            continue
        date = session.get('date', '')
        sevens = norm['total_sevens']
        eights = norm['total_eights']
        nines = norm['total_nines']
        tens = norm['total_tens']
        score = norm['average_score']
        print(f"{date:<20} | {norm['series_count']:<6} | {sevens:<4} | {eights:<3} | {nines:<3} | {tens:<4} | {norm['session_total_100']:<10.2f} | {norm['session_average_100']:<8.2f}")


def create_visualizations(data_manager):
    """Create performance visualizations"""
    sessions = data_manager.get_all_sessions()
    
    if not sessions:
        print("\n❌ No sessions found. Add sessions first.")
        return
    
    print("\n📈 Generating visualizations...")
    
    PerformanceVisualizer.plot_score_trends(sessions)
    PerformanceVisualizer.plot_shot_distribution(sessions)
    PerformanceVisualizer.plot_session_totals(sessions)
    
    if sessions:
        PerformanceVisualizer.plot_performance_pie(sessions[-1])
    
    print("✅ All visualizations created successfully!")
    print("   - score_trends.png")
    print("   - shot_distribution.png")
    print("   - performance_pie.png")


def generate_schedule(data_manager, api):
    """Generate practice schedule"""
    sessions = data_manager.get_all_sessions()
    
    if not sessions:
        print("\n❌ No sessions found. Add sessions first.")
        return
    
    analyses = [api.analyze_session(s) for s in sessions]
    recommendations = api.generate_recommendations(analyses)
    
    print("\n⏱️  GENERATING PRACTICE SCHEDULE")
    print("-" * 40)
    
    days = input("Number of days for schedule (default: 7): ").strip()
    days = int(days) if days.isdigit() else 7
    
    schedule_content = PracticeScheduleGenerator.generate_schedule(recommendations, days)
    print(f"✅ Practice schedule created for {days} days!")
    
    # Display preview safely (handle Unicode)
    try:
        preview = schedule_content[:500]
        print("\n" + preview + "...\n")
    except UnicodeEncodeError:
        # fallback by replacing problematic chars
        preview = schedule_content[:500].encode('utf-8', errors='replace').decode('utf-8')
        print("\n" + preview + "...\n")


def main():
    """Main application loop"""
    data_manager = ShootingDataManager()
    # Wire feedback API key: prefer environment variable, fallback to provided key
    provided_key = os.getenv('SHOOTING_FEEDBACK_API_KEY') or "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"
    api = ShootingPerformanceAPI(api_key=provided_key)
    
    print("\n🎯 Welcome to Pistol Shooting Performance Analyzer!")
    print("   This tool helps track and improve your shooting performance.\n")
    
    while True:
        print_menu()
        choice = input("Select an option (1-8): ").strip()
        
        if choice == '1':
            add_session(data_manager, api)
        elif choice == '2':
            view_statistics(data_manager, api)
        elif choice == '3':
            generate_report(data_manager, api)
        elif choice == '4':
            view_recommendations(data_manager, api)
        elif choice == '5':
            generate_schedule(data_manager, api)
        elif choice == '6':
            create_visualizations(data_manager)
        elif choice == '7':
            view_all_sessions(data_manager)
        elif choice == '8':
            print("\n👋 Thank you for using Pistol Shooting Performance Analyzer!")
            print("   Keep practicing and improving!\n")
            break
        else:
            print("❌ Invalid option. Please select 1-8.")


if __name__ == "__main__":
    main()



