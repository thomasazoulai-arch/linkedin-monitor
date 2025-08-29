#!/usr/bin/env python3
"""
LinkedIn Monitor Agent - Version Production Simplifiée
Dépendance unique: requests
"""
import requests
import csv
import time
import json
import hashlib
import smtplib
import sys
import traceback
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class ProfileData:
    """Structure simple pour un profil LinkedIn"""
    
    def __init__(self, url: str, name: str, last_post_id: str = "", error_count: int = 0):
        self.url = url.strip()
        self.name = name.strip() 
        self.last_post_id = last_post_id.strip()
        self.error_count = error_count
        self.last_check = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, str]:
        return {
            'URL': self.url,
            'Name': self.name, 
            'Last_Post_ID': self.last_post_id,
            'Error_Count': str(self.error_count)
        }


class ContentAnalyzer:
    """Analyseur de contenu LinkedIn simplifié mais efficace"""
    
    @staticmethod
    def analyze_content(html_content: str) -> Dict[str, Any]:
        """Analyse du contenu avec patterns robustes"""
        try:
            # Patterns de détection d'activité LinkedIn
            activity_patterns = [
                r'feed-shared-update-v2',
                r'feed-shared-actor',
                r'update-components-text',
                r'posted\s+this',
                r'shared\s+this',
                r'published\s+on',
                r'activity-actor',
                r'share-update-card'
            ]
            
            engagement_patterns = [
                r'(\d+)\s*(?:likes?|reactions?)',
                r'(\d+)\s*comments?',
                r'(\d+)\s*shares?',
                r'social-counts'
            ]
            
            # Calcul du score d'activité
            activity_score = 0
            post_count = 0
            
            for pattern in activity_patterns:
                matches = len(re.findall(pattern, html_content, re.IGNORECASE))
                post_count += matches
                activity_score += matches * 3
            
            for pattern in engagement_patterns:
                matches = len(re.findall(pattern, html_content, re.IGNORECASE))
                activity_score += matches * 2
            
            # Génération d'un hash de contenu stable
            # On prend les 15000 premiers caractères pour éviter les variations mineures
            significant_content = html_content[:15000]
            content_hash = hashlib.sha256(
                (significant_content + str(activity_score)).encode('utf-8', errors='ignore')
            ).hexdigest()[:20]
            
            # Extraction d'un aperçu de contenu
            preview = ContentAnalyzer._extract_preview(html_content)
            
            return {
                'content_hash': content_hash,
                'activity_score': activity_score,
                'post_count': post_count,
                'preview': preview,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Erreur analyse contenu: {e}")
            return {
                'content_hash': f"error_{hash(html_content[:1000])}",
                'activity_score': 0,
                'post_count': 0,
                'preview': "Erreur d'analyse",
                'timestamp': datetime.now().isoformat()
            }
    
    @staticmethod
    def _extract_preview(html: str) -> str:
        """Extraction d'un aperçu du contenu"""
        # Recherche de contenu textuel dans les posts
        text_patterns = [
            r'<span[^>]*update-components-text[^>]*>(.*?)</span>',
            r'<div[^>]*feed-shared-text[^>]*>(.*?)</div>',
        ]
        
        for pattern in text_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            if matches:
                # Nettoyage basique du HTML
                preview = re.sub(r'<[^>]+>', '', matches[0])
                preview = re.sub(r'\s+', ' ', preview).strip()
                if len(preview) > 3:
                    return preview[:150] + "..." if len(preview) > 150 else preview
        
        return "Nouvelle activité détectée"


class EmailNotifier:
    """Gestionnaire d'email simplifié"""
    
    def __init__(self, sender_email: str, sender_password: str, recipient_email: str):
        self.sender_email = sender_email
        self.sender_password = sender_password  
        self.recipient_email = recipient_email
    
    def send_notification(self, profile: ProfileData, content_analysis: Dict[str, Any]) -> bool:
        """Envoi de notification email avec contenu enrichi"""
        try:
            # Création du message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = f"🔔 LinkedIn Alert - {profile.name}"
            
            # Contenu texte
            text_content = self._build_text_message(profile, content_analysis)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            # Contenu HTML
            html_content = self._build_html_message(profile, content_analysis)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Envoi SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            return False
    
    def _build_text_message(self, profile: ProfileData, analysis: Dict[str, Any]) -> str:
        """Construction du message texte"""
        return f"""🔔 NOUVELLE ACTIVITÉ LINKEDIN DÉTECTÉE

📋 PROFIL:
• Nom: {profile.name}
• URL: {profile.url}
• Détection: {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}

📊 ANALYSE:
• Score d'activité: {analysis['activity_score']}
• Posts détectés: {analysis['post_count']}
• ID de suivi: {analysis['content_hash']}

📝 APERÇU:
{analysis['preview']}

🤖 Système de veille automatisé LinkedIn
Pour voir le contenu complet, visitez: {profile.url}

---
Agent LinkedIn Monitor - Surveillance 24h/24
"""
    
    def _build_html_message(self, profile: ProfileData, analysis: Dict[str, Any]) -> str:
        """Construction du message HTML"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>LinkedIn Alert</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #0077b5, #005885); color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h1 style="margin: 0; font-size: 24px;">🔔 Nouvelle Activité LinkedIn</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">{profile.name}</p>
    </div>
    
    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0;">
        <h2 style="color: #0077b5; margin-top: 0;">📋 Informations du Profil</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px 0; font-weight: bold; width: 30%;">Nom:</td>
                <td style="padding: 8px 0;">{profile.name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">URL:</td>
                <td style="padding: 8px 0;"><a href="{profile.url}" style="color: #0077b5; text-decoration: none;">{profile.url}</a></td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">Détection:</td>
                <td style="padding: 8px 0;">{datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}</td>
            </tr>
        </table>
    </div>
    
    <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 15px 0;">
        <h2 style="color: #1565c0; margin-top: 0;">📊 Analyse de l'Activité</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px 0; font-weight: bold; width: 30%;">Score d'activité:</td>
                <td style="padding: 8px 0;"><span style="background: #4caf50; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold;">{analysis['activity_score']}</span></td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">Posts détectés:</td>
                <td style="padding: 8px 0;">{analysis['post_count']}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold;">ID de suivi:</td>
                <td style="padding: 8px 0; font-family: monospace; font-size: 12px;">{analysis['content_hash']}</td>
            </tr>
        </table>
    </div>
    
    <div style="background: #f1f8e9; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #4caf50;">
        <h2 style="color: #2e7d32; margin-top: 0;">📝 Aperçu du Contenu</h2>
        <p style="font-style: italic; margin: 0; line-height: 1.6;">"{analysis['preview']}"</p>
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{profile.url}" style="background: #0077b5; color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; display: inline-block; font-weight: bold;">
            👀 Voir sur LinkedIn
        </a>
    </div>
    
    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
    
    <div style="text-align: center; font-size: 12px; color: #666; line-height: 1.4;">
        <p>🤖 <strong>LinkedIn Monitor Agent</strong></p>
        <p>Surveillance automatisée 24h/24 • 7j/7</p>
        <p>Système de veille professionnel</p>
    </div>
</body>
</html>
        """


class LinkedInMonitor:
    """Agent principal de monitoring LinkedIn"""
    
    def __init__(self, csv_file: str, email_config: Dict[str, str]):
        self.csv_file = csv_file
        self.notifier = EmailNotifier(
            email_config['sender_email'],
            email_config['sender_password'],
            email_config['recipient_email']
        )
        
        # Configuration de session HTTP optimisée
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Statistiques
        self.stats = {
            'total': 0,
            'success': 0,
            'changes': 0,
            'notifications': 0,
            'errors': 0
        }
    
    def load_profiles(self) -> List[ProfileData]:
        """Chargement des profils depuis CSV avec gestion d'erreurs robuste"""
        try:
            if not os.path.exists(self.csv_file):
                print(f"❌ Fichier CSV non trouvé: {self.csv_file}")
                return self._create_default_profiles()
            
            profiles = []
            
            # Essai de plusieurs encodages
            for encoding in ['utf-8-sig', 'utf-8', 'iso-8859-1']:
                try:
                    with open(self.csv_file, 'r', encoding=encoding, newline='') as file:
                        reader = csv.DictReader(file)
                        for i, row in enumerate(reader, 1):
                            profile = self._parse_row(row, i)
                            if profile:
                                profiles.append(profile)
                    
                    print(f"✅ {len(profiles)} profils chargés (encodage: {encoding})")
                    return profiles
                    
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"❌ Erreur lecture {encoding}: {e}")
                    continue
            
            print("❌ Impossible de lire le fichier CSV")
            return self._create_default_profiles()
            
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            return self._create_default_profiles()
    
    def _parse_row(self, row: Dict[str, Any], line_num: int) -> Optional[ProfileData]:
        """Parse une ligne CSV en ProfileData"""
        try:
            url = str(row.get('URL', '')).strip()
            name = str(row.get('Name', '')).strip()
            last_id = str(row.get('Last_Post_ID', '')).strip()
            error_count = int(row.get('Error_Count', 0) or 0)
            
            if not url or not name:
                print(f"⚠️ Ligne {line_num}: URL ou nom manquant")
                return None
            
            if not self._is_valid_linkedin_url(url):
                print(f"⚠️ Ligne {line_num}: URL LinkedIn invalide")
                return None
            
            profile = ProfileData(url, name, last_id, error_count)
            print(f"✅ Ligne {line_num}: {name}")
            return profile
            
        except Exception as e:
            print(f"❌ Erreur ligne {line_num}: {e}")
            return None
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validation d'URL LinkedIn"""
        patterns = [
            r'^https://www\.linkedin\.com/company/[^/]+/?(?:posts/?)?$',
            r'^https://www\.linkedin\.com/in/[^/]+/?$'
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def _create_default_profiles(self) -> List[ProfileData]:
        """Création de profils par défaut"""
        defaults = [
            ProfileData("https://www.linkedin.com/company/microsoft/posts/", "Microsoft"),
            ProfileData("https://www.linkedin.com/company/tesla-motors/posts/", "Tesla"),
            ProfileData("https://www.linkedin.com/company/google/posts/", "Google")
        ]
        print("📝 Création de profils par défaut")
        self.save_profiles(defaults)
        return defaults
    
    def check_profile(self, profile: ProfileData) -> Optional[Dict[str, Any]]:
        """Vérification d'un profil avec analyse de contenu"""
        try:
            print(f"🔍 Vérification: {profile.name}")
            
            # Optimisation de l'URL pour récupérer les posts
            check_url = self._optimize_url(profile.url)
            
            # Requête avec retry
            response = self._make_request(check_url)
            if not response:
                profile.error_count += 1
                return None
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}")
                profile.error_count += 1
                return None
            
            # Analyse du contenu
            analysis = ContentAnalyzer.analyze_content(response.text)
            
            print(f"📊 Score: {analysis['activity_score']}, Hash: {analysis['content_hash'][:12]}...")
            
            profile.error_count = 0  # Reset en cas de succès
            return analysis
            
        except Exception as e:
            print(f"❌ Erreur {profile.name}: {e}")
            profile.error_count += 1
            return None
    
    def _optimize_url(self, url: str) -> str:
        """Optimise l'URL pour récupérer les posts"""
        if '/company/' in url and not url.endswith('/posts/'):
            if not url.endswith('/'):
                url += '/'
            if not url.endswith('posts/'):
                url += 'posts/'
        return url
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Requête HTTP avec retry"""
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
                print(f"❌ Tentative {attempt + 1}/3: {e}")
                if attempt < 2:
                    time.sleep(10)
        return None
    
    def save_profiles(self, profiles: List[ProfileData]) -> bool:
        """Sauvegarde des profils en CSV"""
        try:
            fieldnames = ['URL', 'Name', 'Last_Post_ID', 'Error_Count']
            
            with open(self.csv_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for profile in profiles:
                    writer.writerow(profile.to_dict())
            
            print("💾 Profils sauvegardés")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def run_monitoring(self) -> bool:
        """Cycle principal de monitoring"""
        try:
            print("=" * 80)
            print(f"🚀 LINKEDIN MONITORING - {datetime.now()}")
            print("=" * 80)
            
            # Chargement des profils
            profiles = self.load_profiles()
            if not profiles:
                print("❌ Aucun profil à surveiller")
                return False
            
            self.stats['total'] = len(profiles)
            changes_made = False
            
            # Traitement de chaque profil
            for i, profile in enumerate(profiles):
                try:
                    print(f"\n--- {i+1}/{len(profiles)}: {profile.name} ---")
                    print(f"🔗 URL: {profile.url}")
                    print(f"🆔 Dernier ID: {profile.last_post_id[:15]}..." if profile.last_post_id else "🆔 Première vérification")
                    
                    # Vérification
                    analysis = self.check_profile(profile)
                    
                    if analysis:
                        self.stats['success'] += 1
                        current_id = analysis['content_hash']
                        
                        # Détection de changement
                        if profile.last_post_id != current_id:
                            print(f"🆕 CHANGEMENT DÉTECTÉ!")
                            self.stats['changes'] += 1
                            changes_made = True
                            
                            # Mise à jour
                            profile.last_post_id = current_id
                            
                            # Notification
                            if self.notifier.send_notification(profile, analysis):
                                self.stats['notifications'] += 1
                                print("✅ Notification envoyée")
                            else:
                                print("❌ Échec notification")
                        else:
                            print("⚪ Aucun changement")
                    else:
                        self.stats['errors'] += 1
                    
                    # Pause entre les profils
                    if i < len(profiles) - 1:
                        pause = 15 + (i % 3) * 5  # 15-25 secondes
                        print(f"⏳ Pause {pause}s...")
                        time.sleep(pause)
                
                except Exception as e:
                    print(f"❌ Erreur traitement {profile.name}: {e}")
                    self.stats['errors'] += 1
            
            # Sauvegarde
            if changes_made:
                self.save_profiles(profiles)
            
            # Rapport final
            self._print_report()
            
            return self.stats['success'] > 0
            
        except Exception as e:
            print(f"💥 ERREUR CRITIQUE: {e}")
            traceback.print_exc()
            return False
    
    def _print_report(self):
        """Rapport final"""
        print("\n" + "=" * 80)
        print("📊 RAPPORT FINAL")
        print("=" * 80)
        print(f"📋 Profils traités: {self.stats['success']}/{self.stats['total']}")
        print(f"🆕 Changements: {self.stats['changes']}")
        print(f"📧 Notifications: {self.stats['notifications']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        
        success_rate = (self.stats['success'] / self.stats['total']) * 100 if self.stats['total'] > 0 else 0
        print(f"📈 Taux de succès: {success_rate:.1f}%")
        print("=" * 80)


def validate_environment() -> Dict[str, str]:
    """Validation de l'environnement"""
    print("🔧 Validation de l'environnement...")
    
    required_vars = {
        'GMAIL_EMAIL': 'sender_email',
        'GMAIL_APP_PASSWORD': 'sender_password', 
        'RECIPIENT_EMAIL': 'recipient_email'
    }
    
    config = {}
    missing = []
    
    for env_var, config_key in required_vars.items():
        value = os.getenv(env_var, '').strip()
        if value:
            config[config_key] = value
            # Affichage sécurisé (masque partiellement)
            display_value = value[:3] + "*" * (len(value)-6) + value[-3:] if len(value) > 6 else "***"
            print(f"✅ {env_var}: {display_value}")
        else:
            missing.append(env_var)
            print(f"❌ {env_var}: MANQUANT")
    
    if missing:
        print(f"\n💥 Variables manquantes: {', '.join(missing)}")
        print("💡 Configurez dans GitHub Secrets:")
        print("   Repository → Settings → Secrets and variables → Actions")
        raise ValueError(f"Configuration incomplète: {missing}")
    
    print("✅ Configuration validée")
    return config


def main():
    """Point d'entrée principal"""
    try:
        print("🎯" + "=" * 78 + "🎯")
        print("🤖 LINKEDIN MONITORING AGENT - VERSION SIMPLIFIÉE")
        print("🎯" + "=" * 78 + "🎯")
        
        # Validation
        email_config = validate_environment()
        
        # Monitoring
        monitor = LinkedInMonitor("linkedin_urls.csv", email_config)
        success = monitor.run_monitoring()
        
        # Résultat
        if success:
            print("🎉 MONITORING TERMINÉ AVEC SUCCÈS")
            sys.exit(0)
        else:
            print("💥 ÉCHEC DU MONITORING")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt demandé")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 ERREUR FATALE: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
