#!/usr/bin/env python3
"""
LinkedIn Monitor Agent - Version Expert Python
Architecture modulaire et détection avancée
"""
import requests
import csv
import time
import json
import hashlib
import smtplib
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import os
from urllib.parse import urljoin, urlparse


@dataclass
class ProfileData:
    """Structure de données pour un profil LinkedIn"""
    url: str
    name: str
    last_post_id: str = ""
    last_check: Optional[str] = None
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, str]:
        return {
            'URL': self.url,
            'Name': self.name,
            'Last_Post_ID': self.last_post_id,
            'Last_Check': self.last_check or '',
            'Error_Count': str(self.error_count)
        }


@dataclass 
class ContentAnalysis:
    """Résultat d'analyse de contenu LinkedIn"""
    content_hash: str
    activity_score: int
    post_count: int
    engagement_indicators: int
    has_recent_activity: bool
    content_preview: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class LinkedInContentDetector:
    """Détecteur avancé de contenu LinkedIn"""
    
    # Patterns sophistiqués pour détecter l'activité
    ACTIVITY_PATTERNS = {
        'posts': [
            r'feed-shared-update-v2__activity-header',
            r'feed-shared-actor__name',
            r'feed-shared-text',
            r'posted\s+this',
            r'shared\s+this',
            r'published\s+on\s+linkedin',
            r'update-components-text'
        ],
        'engagement': [
            r'(\d+)\s*(?:likes?|reactions?)',
            r'(\d+)\s*comments?',
            r'(\d+)\s*shares?',
            r'(\d+)\s*reposts?',
            r'social-counts-reactions'
        ],
        'timestamps': [
            r'(\d+[smhd])\s*ago',
            r'(\d+)\s*(?:second|minute|hour|day)s?\s*ago',
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        ],
        'content_types': [
            r'video-type-indicator',
            r'image-type-indicator', 
            r'document-type-indicator',
            r'poll-type-indicator',
            r'carousel-type-indicator'
        ]
    }
    
    @classmethod
    def analyze_content(cls, html_content: str) -> ContentAnalysis:
        """Analyse avancée du contenu LinkedIn"""
        try:
            activity_score = 0
            post_count = 0
            engagement_indicators = 0
            recent_activity = False
            
            # Analyse des patterns par catégorie
            for category, patterns in cls.ACTIVITY_PATTERNS.items():
                category_matches = 0
                
                for pattern in patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    match_count = len(matches)
                    category_matches += match_count
                    
                    if category == 'posts':
                        post_count += match_count
                        activity_score += match_count * 5  # Posts ont plus de poids
                    elif category == 'engagement':
                        engagement_indicators += match_count
                        activity_score += match_count * 2
                    elif category == 'timestamps':
                        # Détection d'activité récente
                        for match in matches:
                            if any(recent in str(match).lower() for recent in ['1h', '2h', '3h', '1d', '2d']):
                                recent_activity = True
                                activity_score += 10
                    elif category == 'content_types':
                        activity_score += match_count * 3
            
            # Génération d'un hash de contenu plus précis
            significant_content = cls._extract_significant_content(html_content)
            content_hash = hashlib.sha256(
                (significant_content + str(activity_score)).encode('utf-8', errors='ignore')
            ).hexdigest()[:24]  # Hash plus long pour éviter les collisions
            
            # Extraction d'un aperçu de contenu
            content_preview = cls._extract_content_preview(html_content)
            
            return ContentAnalysis(
                content_hash=content_hash,
                activity_score=activity_score,
                post_count=post_count,
                engagement_indicators=engagement_indicators,
                has_recent_activity=recent_activity,
                content_preview=content_preview
            )
            
        except Exception as e:
            print(f"❌ Erreur analyse contenu: {e}")
            return ContentAnalysis(
                content_hash="error_" + str(hash(html_content[:1000])),
                activity_score=0,
                post_count=0, 
                engagement_indicators=0,
                has_recent_activity=False
            )
    
    @staticmethod
    def _extract_significant_content(html: str) -> str:
        """Extrait le contenu significatif pour le hashing"""
        # Suppression du contenu non-significatif
        patterns_to_remove = [
            r'<script[^>]*>.*?</script>',
            r'<style[^>]*>.*?</style>',
            r'<!--.*?-->',
            r'class="[^"]*"',
            r'id="[^"]*"',
            r'style="[^"]*"'
        ]
        
        cleaned = html
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        return cleaned[:15000]  # Limite pour éviter les hash trop longs
    
    @staticmethod
    def _extract_content_preview(html: str) -> str:
        """Extrait un aperçu du contenu pour les notifications"""
        # Patterns pour extraire le contenu textuel des posts
        content_patterns = [
            r'<span[^>]*class="[^"]*feed-shared-text[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*update-components-text[^"]*"[^>]*>(.*?)</div>',
        ]
        
        for pattern in content_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            if matches:
                # Nettoyage du HTML et troncature
                preview = re.sub(r'<[^>]+>', '', matches[0])
                preview = re.sub(r'\s+', ' ', preview).strip()
                return preview[:200] + "..." if len(preview) > 200 else preview
        
        return "Contenu détecté mais non extractible"


class EmailNotifier:
    """Gestionnaire d'email avancé avec templates"""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
    
    def send_change_notification(self, profile: ProfileData, analysis: ContentAnalysis) -> bool:
        """Envoi notification de changement avec contenu enrichi"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.config['sender_email']
            msg['To'] = self.config['recipient_email']
            msg['Subject'] = f"🔔 LinkedIn Alert - {profile.name}"
            
            # Version texte
            text_content = self._build_text_notification(profile, analysis)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            # Version HTML (optionnel)
            html_content = self._build_html_notification(profile, analysis)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            return self._send_email(msg)
            
        except Exception as e:
            print(f"❌ Erreur création email: {e}")
            return False
    
    def _build_text_notification(self, profile: ProfileData, analysis: ContentAnalysis) -> str:
        """Construction du message texte"""
        dt = datetime.fromisoformat(analysis.timestamp.replace('Z', '+00:00'))
        date_str = dt.strftime('%d/%m/%Y à %H:%M UTC')
        
        return f"""🔔 NOUVELLE ACTIVITÉ LINKEDIN DÉTECTÉE

📋 PROFIL:
• Nom: {profile.name}
• URL: {profile.url}
• Détection: {date_str}

📊 ANALYSE:
• Score d'activité: {analysis.activity_score}
• Nouveaux posts: {analysis.post_count}
• Indicateurs d'engagement: {analysis.engagement_indicators}
• Activité récente: {'✅ Oui' if analysis.has_recent_activity else '❌ Non'}
• ID de suivi: {analysis.content_hash}

📝 APERÇU:
{analysis.content_preview}

🤖 Système de veille automatisé LinkedIn
Pour consulter le contenu complet, visitez l'URL ci-dessus.
"""
    
    def _build_html_notification(self, profile: ProfileData, analysis: ContentAnalysis) -> str:
        """Construction du message HTML"""
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #0077b5;">🔔 Nouvelle Activité LinkedIn</h2>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h3 style="margin-top: 0;">📋 Profil</h3>
                <p><strong>Nom:</strong> {profile.name}</p>
                <p><strong>URL:</strong> <a href="{profile.url}" style="color: #0077b5;">{profile.url}</a></p>
            </div>
            
            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h3 style="margin-top: 0;">📊 Analyse</h3>
                <p><strong>Score d'activité:</strong> {analysis.activity_score}</p>
                <p><strong>Nouveaux posts:</strong> {analysis.post_count}</p>
                <p><strong>Engagement:</strong> {analysis.engagement_indicators} indicateurs</p>
                <p><strong>Activité récente:</strong> {'✅ Oui' if analysis.has_recent_activity else '❌ Non'}</p>
            </div>
            
            <div style="background: #f1f8e9; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h3 style="margin-top: 0;">📝 Aperçu du Contenu</h3>
                <p style="font-style: italic;">{analysis.content_preview}</p>
            </div>
            
            <hr style="margin: 20px 0;">
            <p style="font-size: 12px; color: #666;">
                🤖 Système de veille automatisé LinkedIn<br>
                ID de suivi: {analysis.content_hash}<br>
                Détection: {analysis.timestamp}
            </p>
        </div>
        </body>
        </html>
        """
    
    def _send_email(self, msg: MIMEMultipart) -> bool:
        """Envoi SMTP sécurisé"""
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.config['sender_email'], self.config['sender_password'])
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"❌ Erreur SMTP: {e}")
            return False


class LinkedInMonitor:
    """Agent principal de monitoring LinkedIn - Version Expert"""
    
    def __init__(self, csv_file_path: str, email_config: Dict[str, str]):
        self.csv_file_path = Path(csv_file_path)
        self.notifier = EmailNotifier(email_config)
        self.session = self._create_session()
        self.stats = {
            'total_profiles': 0,
            'successful_checks': 0,
            'changes_detected': 0,
            'notifications_sent': 0,
            'errors': 0,
            'start_time': datetime.now(timezone.utc)
        }
    
    def _create_session(self) -> requests.Session:
        """Création d'une session HTTP optimisée"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
        # Configuration des timeouts et retry
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=2))
        return session
    
    def load_profiles(self) -> List[ProfileData]:
        """Chargement et validation des profils depuis CSV"""
        try:
            if not self.csv_file_path.exists():
                print(f"❌ Fichier CSV non trouvé: {self.csv_file_path}")
                return self._create_default_profiles()
            
            profiles = []
            with open(self.csv_file_path, 'r', encoding='utf-8-sig', newline='') as file:
                reader = csv.DictReader(file)
                
                for i, row in enumerate(reader, 1):
                    try:
                        profile = self._parse_profile_row(row)
                        if profile:
                            profiles.append(profile)
                            print(f"✅ Profil {i}: {profile.name}")
                        else:
                            print(f"⚠️ Profil {i} ignoré: données invalides")
                    except Exception as e:
                        print(f"❌ Erreur ligne {i}: {e}")
                        continue
            
            print(f"📋 {len(profiles)} profils chargés avec succès")
            return profiles
            
        except Exception as e:
            print(f"❌ Erreur chargement CSV: {e}")
            return self._create_default_profiles()
    
    def _parse_profile_row(self, row: Dict[str, Any]) -> Optional[ProfileData]:
        """Parse une ligne CSV en ProfileData"""
        url = str(row.get('URL', '')).strip()
        name = str(row.get('Name', '')).strip()
        
        if not url or not name or not self._is_valid_linkedin_url(url):
            return None
        
        return ProfileData(
            url=url,
            name=name,
            last_post_id=str(row.get('Last_Post_ID', '')).strip(),
            last_check=str(row.get('Last_Check', '')).strip() or None,
            error_count=int(row.get('Error_Count', 0) or 0)
        )
    
    def _create_default_profiles(self) -> List[ProfileData]:
        """Création de profils par défaut"""
        defaults = [
            ProfileData("https://www.linkedin.com/company/microsoft/posts/", "Microsoft"),
            ProfileData("https://www.linkedin.com/company/tesla-motors/posts/", "Tesla"),
            ProfileData("https://www.linkedin.com/company/google/posts/", "Google")
        ]
        
        self.save_profiles(defaults)
        return defaults
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validation d'URL LinkedIn améliorée"""
        parsed = urlparse(url)
        if parsed.netloc != 'www.linkedin.com':
            return False
        
        valid_patterns = [
            r'^/company/[^/]+/?(?:posts/?)?$',
            r'^/in/[^/]+/?$',
            r'^/company/[^/]+/posts/?$'
        ]
        
        return any(re.match(pattern, parsed.path) for pattern in valid_patterns)
    
    def check_profile(self, profile: ProfileData) -> Tuple[bool, Optional[ContentAnalysis]]:
        """Vérification d'un profil avec analyse avancée"""
        try:
            print(f"🔍 Vérification: {profile.name}")
            
            # Optimisation de l'URL pour les posts
            check_url = self._optimize_url_for_posts(profile.url)
            
            # Requête avec gestion d'erreurs
            response = self._make_request(check_url)
            if not response or response.status_code != 200:
                profile.error_count += 1
                return False, None
            
            # Analyse du contenu
            analysis = LinkedInContentDetector.analyze_content(response.text)
            
            print(f"📊 Score: {analysis.activity_score}, Hash: {analysis.content_hash[:12]}...")
            
            # Reset du compteur d'erreurs en cas de succès
            profile.error_count = 0
            profile.last_check = datetime.now(timezone.utc).isoformat()
            
            return True, analysis
            
        except Exception as e:
            print(f"❌ Erreur vérification {profile.name}: {e}")
            profile.error_count += 1
            return False, None
    
    def _optimize_url_for_posts(self, url: str) -> str:
        """Optimise l'URL pour récupérer les posts"""
        if '/company/' in url and not url.endswith('/posts/'):
            if not url.endswith('/'):
                url += '/'
            if not url.endswith('posts/'):
                url += 'posts/'
        return url
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Requête HTTP avec retry et timeouts"""
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code == 429:  # Rate limiting
                    wait_time = 60 + (attempt * 30)
                    print(f"⏰ Rate limit, attente {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                return response
            except requests.exceptions.RequestException as e:
                print(f"❌ Tentative {attempt + 1}/3 échouée: {e}")
                if attempt < 2:
                    time.sleep(10 * (attempt + 1))
        return None
    
    def save_profiles(self, profiles: List[ProfileData]) -> bool:
        """Sauvegarde des profils avec gestion d'erreurs"""
        try:
            fieldnames = ['URL', 'Name', 'Last_Post_ID', 'Last_Check', 'Error_Count']
            
            with open(self.csv_file_path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                
                for profile in profiles:
                    writer.writerow(profile.to_dict())
            
            print("💾 Profils sauvegardés")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def run_monitoring_cycle(self) -> bool:
        """Cycle principal de monitoring optimisé"""
        try:
            print("=" * 80)
            print(f"🚀 DÉBUT MONITORING - {datetime.now(timezone.utc)}")
            print("=" * 80)
            
            # Chargement des profils
            profiles = self.load_profiles()
            if not profiles:
                print("❌ Aucun profil à monitorer")
                return False
            
            self.stats['total_profiles'] = len(profiles)
            changes_detected = False
            
            # Traitement de chaque profil
            for i, profile in enumerate(profiles):
                try:
                    print(f"\n--- {i+1}/{len(profiles)}: {profile.name} ---")
                    
                    # Vérification du profil
                    success, analysis = self.check_profile(profile)
                    
                    if success and analysis:
                        self.stats['successful_checks'] += 1
                        
                        # Détection de changement
                        if profile.last_post_id != analysis.content_hash:
                            print(f"🆕 CHANGEMENT DÉTECTÉ!")
                            self.stats['changes_detected'] += 1
                            changes_detected = True
                            
                            # Mise à jour et notification
                            profile.last_post_id = analysis.content_hash
                            
                            if self.notifier.send_change_notification(profile, analysis):
                                self.stats['notifications_sent'] += 1
                                print("✅ Notification envoyée")
                            else:
                                print("❌ Échec notification")
                        else:
                            print("⚪ Aucun changement")
                    else:
                        self.stats['errors'] += 1
                    
                    # Pause adaptative entre vérifications
                    if i < len(profiles) - 1:
                        pause = min(15 + (i % 3) * 5, 30)  # 15-30s
                        print(f"⏳ Pause {pause}s...")
                        time.sleep(pause)
                        
                except Exception as e:
                    print(f"❌ Erreur traitement {profile.name}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            # Sauvegarde des modifications
            if changes_detected:
                self.save_profiles(profiles)
            
            self._print_final_report()
            return self.stats['successful_checks'] > 0
            
        except Exception as e:
            print(f"💥 ERREUR CRITIQUE: {e}")
            traceback.print_exc()
            return False
    
    def _print_final_report(self):
        """Rapport final détaillé"""
        duration = datetime.now(timezone.utc) - self.stats['start_time']
        
        print("\n" + "=" * 80)
        print("📊 RAPPORT FINAL DE MONITORING")
        print("=" * 80)
        print(f"⏱️  Durée d'exécution: {duration}")
        print(f"📋 Profils traités: {self.stats['successful_checks']}/{self.stats['total_profiles']}")
        print(f"🆕 Changements détectés: {self.stats['changes_detected']}")
        print(f"📧 Notifications envoyées: {self.stats['notifications_sent']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        
        success_rate = (self.stats['successful_checks'] / self.stats['total_profiles']) * 100 if self.stats['total_profiles'] > 0 else 0
        print(f"📈 Taux de succès: {success_rate:.1f}%")
        print("=" * 80)


def validate_environment() -> Dict[str, str]:
    """Validation de l'environnement avec diagnostics détaillés"""
    print("🔧 Validation de l'environnement...")
    
    required_vars = ['GMAIL_EMAIL', 'GMAIL_APP_PASSWORD', 'RECIPIENT_EMAIL']
    config = {}
    missing = []
    
    for var in required_vars:
        value = os.getenv(var, '').strip()
        if value:
            config[var.lower().replace('gmail_', 'sender_').replace('app_', '')] = value
            print(f"✅ {var}: {'*' * (len(value) - 4) + value[-4:] if len(value) > 4 else '***'}")
        else:
            missing.append(var)
            print(f"❌ {var}: NON DÉFINI")
    
    if missing:
        print(f"\n💥 Variables manquantes: {', '.join(missing)}")
        print("📖 Guide configuration:")
        print("   1. Repository → Settings → Secrets and variables → Actions")
        print("   2. Ajoutez chaque variable avec sa valeur")
        print("   3. Pour GMAIL_APP_PASSWORD: utilisez un mot de passe d'application Gmail")
        raise ValueError(f"Configuration incomplète: {missing}")
    
    print("✅ Configuration validée")
    return config


def main():
    """Point d'entrée principal expert"""
    try:
        print("🎯" + "=" * 78 + "🎯")
        print("🤖 LINKEDIN MONITORING AGENT - VERSION EXPERT PYTHON")
        print("🎯" + "=" * 78 + "🎯")
        
        # Validation et configuration
        email_config = validate_environment()
        
        # Initialisation de l'agent
        monitor = LinkedInMonitor("linkedin_urls.csv", email_config)
        
        # Exécution du monitoring
        success = monitor.run_monitoring_cycle()
        
        # Code de sortie
        if success:
            print("🎉 MONITORING TERMINÉ AVEC SUCCÈS")
            sys.exit(0)
        else:
            print("💥 ÉCHEC DU MONITORING")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt demandé par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 ERREUR FATALE: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
