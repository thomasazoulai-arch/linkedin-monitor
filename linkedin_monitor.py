#!/usr/bin/env python3
"""
LinkedIn Monitor - Version Corrigée et Simplifiée
Système d'alerte robuste pour nouveaux posts LinkedIn
Version: 2.0 - Production Ready
"""

import requests
import csv
import time
import hashlib
import smtplib
import os
import sys
import re
import json
from datetime import datetime
from typing import List, Dict, Optional, NamedTuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote
import traceback


class LinkedInPost(NamedTuple):
    """Structure d'un post LinkedIn détecté"""
    profile_name: str
    title: str
    description: str
    url: str
    detected_at: str


class LinkedInProfile:
    """Profil LinkedIn à surveiller"""
    
    def __init__(self, url: str, name: str, last_hash: str = "", error_count: int = 0):
        self.url = self._normalize_url(url)
        self.name = name.strip()
        self.last_hash = last_hash.strip()
        self.error_count = error_count
        self.last_check = datetime.now().isoformat()
    
    def _normalize_url(self, url: str) -> str:
        """Normalise l'URL LinkedIn"""
        url = url.strip()
        
        # Assurer HTTPS
        if url.startswith('http://'):
            url = url.replace('http://', 'https://')
        elif not url.startswith('https://'):
            url = 'https://' + url
        
        # Ajouter posts pour les companies si pas présent
        if '/company/' in url and not url.endswith('/posts/') and not url.endswith('/posts'):
            if not url.endswith('/'):
                url += '/'
            url += 'posts/'
        
        return url
    
    def is_valid(self) -> bool:
        """Vérifie si l'URL est valide"""
        patterns = [
            r'^https://www\.linkedin\.com/company/[^/]+/?(?:posts/?)?$',
            r'^https://www\.linkedin\.com/in/[^/]+/?$'
        ]
        return any(re.match(pattern, self.url) for pattern in patterns)
    
    def to_dict(self) -> Dict[str, str]:
        """Conversion en dictionnaire pour CSV"""
        return {
            'URL': self.url,
            'Name': self.name,
            'Last_Post_ID': self.last_hash,
            'Error_Count': str(self.error_count)
        }


class ContentExtractor:
    """Extracteur de contenu LinkedIn simplifié et robuste"""
    
    @staticmethod
    def extract_activity_hash(html_content: str, profile_name: str) -> Tuple[str, Optional[LinkedInPost]]:
        """Extrait un hash de l'activité et détecte les nouveaux posts"""
        try:
            if not html_content or len(html_content) < 100:
                return f"empty_{int(time.time())}", None
            
            # Patterns de détection d'activité LinkedIn
            activity_patterns = [
                r'data-urn="urn:li:activity:(\d+)"',
                r'activity-(\d+)',
                r'urn:li:activity:(\d+)',
                r'"activityUrn":"urn:li:activity:(\d+)"'
            ]
            
            activity_ids = []
            for pattern in activity_patterns:
                matches = re.findall(pattern, html_content)
                activity_ids.extend(matches)
            
            # Patterns de contenu de posts
            content_patterns = [
                r'<span[^>]*update-components-text[^>]*>([^<]{20,200})</span>',
                r'"text":"([^"]{20,200})"',
                r'<div[^>]*feed-shared-text[^>]*>([^<]{20,200})</div>'
            ]
            
            content_snippets = []
            for pattern in content_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                content_snippets.extend(matches[:3])  # Limiter à 3 extraits
            
            # Créer un hash basé sur le contenu détecté
            hash_content = ""
            
            if activity_ids:
                # Utiliser les IDs d'activité les plus récents
                recent_ids = sorted(set(activity_ids), reverse=True)[:5]
                hash_content += "ids:" + ",".join(recent_ids)
            
            if content_snippets:
                # Nettoyer et ajouter les extraits de contenu
                clean_snippets = []
                for snippet in content_snippets:
                    clean = ContentExtractor._clean_text(snippet)
                    if len(clean) > 20:
                        clean_snippets.append(clean)
                
                hash_content += "content:" + "|".join(clean_snippets[:3])
            
            # Si aucun contenu détecté, utiliser une signature de la page
            if not hash_content:
                page_signature = re.findall(r'linkedin\.com/[^"\'>\s]+', html_content)[:5]
                hash_content = "signature:" + ",".join(page_signature)
            
            # Générer le hash final
            content_hash = hashlib.sha256(hash_content.encode('utf-8')).hexdigest()[:16]
            
            # Créer un post si du nouveau contenu est détecté
            new_post = None
            if content_snippets and activity_ids:
                latest_content = ContentExtractor._clean_text(content_snippets[0])
                latest_activity = activity_ids[0] if activity_ids else "unknown"
                
                post_url = f"https://www.linkedin.com/posts/activity-{latest_activity}"
                
                new_post = LinkedInPost(
                    profile_name=profile_name,
                    title=latest_content[:80] + "..." if len(latest_content) > 80 else latest_content,
                    description=f"Nouvelle publication de {profile_name}. {latest_content[:150]}...",
                    url=post_url,
                    detected_at=datetime.now().strftime('%d/%m/%Y à %H:%M')
                )
            
            return content_hash, new_post
            
        except Exception as e:
            print(f"❌ Erreur extraction contenu: {e}")
            return f"error_{int(time.time())}", None
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Nettoie le texte extrait"""
        if not text:
            return ""
        
        # Supprimer balises HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        # Décoder entités HTML communes
        html_entities = {
            '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&#39;': "'", '&nbsp;': ' '
        }
        
        for entity, char in html_entities.items():
            text = text.replace(entity, char)
        
        # Nettoyer espaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text


class EmailNotifier:
    """Gestionnaire d'emails simplifié"""
    
    def __init__(self, sender_email: str, sender_password: str, recipient_email: str):
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipient_email = recipient_email
    
    def send_notification(self, new_posts: List[LinkedInPost]) -> bool:
        """Envoie une notification pour les nouveaux posts"""
        try:
            if not new_posts:
                print("ℹ️ Aucun nouveau post - Pas d'email envoyé")
                return True
            
            print(f"📧 Envoi notification pour {len(new_posts)} nouveau(x) post(s)...")
            
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = f"🔔 LinkedIn Alert - {len(new_posts)} nouveau(x) post(s)"
            
            # Contenu texte
            text_content = self._build_text_content(new_posts)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            # Contenu HTML
            html_content = self._build_html_content(new_posts)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Envoi via Gmail SMTP
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"✅ Email envoyé avec succès pour {len(new_posts)} post(s)")
            return True
            
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            return False
    
    def _build_text_content(self, posts: List[LinkedInPost]) -> str:
        """Construit le contenu texte de l'email"""
        content = f"""🔔 NOUVEAUX POSTS LINKEDIN DÉTECTÉS

📅 Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M UTC')}
📊 {len(posts)} nouveau(x) post(s) publié(s)

"""
        
        for i, post in enumerate(posts, 1):
            content += f"""--- POST #{i} ---
👤 Profil: {post.profile_name}
📝 Titre: {post.title}
📄 Description: {post.description}
🔗 URL: {post.url}
⏰ Détecté: {post.detected_at}

"""
        
        content += """🤖 LinkedIn Monitor - Surveillance automatisée
Système d'alerte pour nouveaux posts LinkedIn"""
        
        return content
    
    def _build_html_content(self, posts: List[LinkedInPost]) -> str:
        """Construit le contenu HTML de l'email"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>LinkedIn Alert</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #0077b5; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; }}
        .post {{ background: #f8f9fa; border-left: 4px solid #0077b5; margin: 15px 0; padding: 15px; border-radius: 5px; }}
        .footer {{ text-align: center; font-size: 12px; color: #666; margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; }}
        .url {{ word-break: break-all; color: #0077b5; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔔 Nouveaux Posts LinkedIn</h1>
        <p>{len(posts)} nouveau(x) post(s) détecté(s) le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
    </div>
"""
        
        for i, post in enumerate(posts, 1):
            html += f"""
    <div class="post">
        <h3>📝 POST #{i}: {post.profile_name}</h3>
        <p><strong>Titre:</strong> {post.title}</p>
        <p><strong>Description:</strong> {post.description}</p>
        <p><strong>URL:</strong> <a href="{post.url}" class="url" target="_blank">{post.url}</a></p>
        <p><strong>Détecté:</strong> {post.detected_at}</p>
    </div>
"""
        
        html += """
    <div class="footer">
        <p><strong>🤖 LinkedIn Monitor</strong></p>
        <p>Système d'alerte automatisé pour nouveaux posts LinkedIn</p>
    </div>
</body>
</html>
"""
        return html


class CSVManager:
    """Gestionnaire de fichiers CSV"""
    
    @staticmethod
    def load_profiles(csv_file: str) -> List[LinkedInProfile]:
        """Charge les profils depuis le fichier CSV"""
        try:
            if not os.path.exists(csv_file):
                print(f"❌ Fichier {csv_file} non trouvé, création par défaut...")
                return CSVManager._create_default_profiles(csv_file)
            
            profiles = []
            
            # Essayer différents encodages
            encodings = ['utf-8-sig', 'utf-8', 'iso-8859-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(csv_file, 'r', encoding=encoding, newline='') as file:
                        reader = csv.DictReader(file)
                        profiles = []
                        
                        for i, row in enumerate(reader, 1):
                            try:
                                url = str(row.get('URL', '')).strip()
                                name = str(row.get('Name', '')).strip()
                                last_hash = str(row.get('Last_Post_ID', '')).strip()
                                error_count = int(row.get('Error_Count', 0) or 0)
                                
                                if url and name:
                                    profile = LinkedInProfile(url, name, last_hash, error_count)
                                    if profile.is_valid():
                                        profiles.append(profile)
                                        print(f"✅ Profil {i}: {name}")
                                    else:
                                        print(f"⚠️ Profil {i} invalide: {url}")
                                else:
                                    print(f"⚠️ Ligne {i}: données manquantes")
                                    
                            except Exception as e:
                                print(f"❌ Erreur ligne {i}: {e}")
                    
                    print(f"✅ {len(profiles)} profils chargés (encodage: {encoding})")
                    return profiles
                    
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"❌ Erreur lecture {encoding}: {e}")
                    continue
            
            print("❌ Impossible de lire le fichier CSV")
            return CSVManager._create_default_profiles(csv_file)
            
        except Exception as e:
            print(f"❌ Erreur chargement CSV: {e}")
            return []
    
    @staticmethod
    def save_profiles(csv_file: str, profiles: List[LinkedInProfile]) -> bool:
        """Sauvegarde les profils dans le fichier CSV"""
        try:
            fieldnames = ['URL', 'Name', 'Last_Post_ID', 'Error_Count']
            
            with open(csv_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                
                for profile in profiles:
                    writer.writerow(profile.to_dict())
            
            print(f"✅ {len(profiles)} profils sauvegardés")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde CSV: {e}")
            return False
    
    @staticmethod
    def _create_default_profiles(csv_file: str) -> List[LinkedInProfile]:
        """Crée des profils par défaut"""
        defaults = [
            LinkedInProfile("https://www.linkedin.com/company/microsoft/posts/", "Microsoft"),
            LinkedInProfile("https://www.linkedin.com/company/google/posts/", "Google"),
            LinkedInProfile("https://www.linkedin.com/company/tesla-motors/posts/", "Tesla")
        ]
        
        CSVManager.save_profiles(csv_file, defaults)
        print(f"✅ Fichier par défaut créé avec {len(defaults)} profils")
        return defaults


class WebScraper:
    """Scraper web robuste pour LinkedIn"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
    
    def fetch_profile_content(self, url: str) -> Optional[str]:
        """Récupère le contenu d'un profil LinkedIn"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                print(f"🌐 Requête {attempt + 1}/{max_retries}: {url}")
                
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    print(f"✅ Contenu récupéré ({len(response.text)} caractères)")
                    return response.text
                elif response.status_code == 429:
                    wait_time = 60 + (attempt * 30)
                    print(f"⏰ Rate limit (429), attente {wait_time}s...")
                    time.sleep(wait_time)
                elif response.status_code == 403:
                    print(f"🚫 Accès refusé (403) - LinkedIn bloque la requête")
                    return None
                else:
                    print(f"❌ Erreur HTTP {response.status_code}")
                
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout sur tentative {attempt + 1}")
            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur requête {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 10 + (attempt * 10)
                print(f"⏳ Attente {wait_time}s avant retry...")
                time.sleep(wait_time)
        
        print("❌ Échec récupération après tous les essais")
        return None


class LinkedInMonitor:
    """Agent principal de monitoring LinkedIn"""
    
    def __init__(self, csv_file: str = "linkedin_urls.csv"):
        self.csv_file = csv_file
        self.scraper = WebScraper()
        self.notifier = None
        self.stats = {
            'total': 0,
            'success': 0,
            'changes': 0,
            'new_posts': 0,
            'errors': 0
        }
    
    def setup_email(self) -> bool:
        """Configure les paramètres email depuis les variables d'environnement"""
        try:
            sender_email = os.getenv('GMAIL_EMAIL', '').strip()
            sender_password = os.getenv('GMAIL_APP_PASSWORD', '').strip()
            recipient_email = os.getenv('RECIPIENT_EMAIL', '').strip()
            
            missing = []
            if not sender_email:
                missing.append('GMAIL_EMAIL')
            if not sender_password:
                missing.append('GMAIL_APP_PASSWORD')
            if not recipient_email:
                missing.append('RECIPIENT_EMAIL')
            
            if missing:
                print(f"❌ Variables manquantes: {', '.join(missing)}")
                return False
            
            self.notifier = EmailNotifier(sender_email, sender_password, recipient_email)
            print("✅ Configuration email validée")
            return True
            
        except Exception as e:
            print(f"❌ Erreur configuration email: {e}")
            return False
    
    def check_profile(self, profile: LinkedInProfile) -> Optional[LinkedInPost]:
        """Vérifie un profil et détecte les changements"""
        try:
            print(f"\n🔍 Vérification: {profile.name}")
            print(f"🔗 URL: {profile.url}")
            
            # Récupérer le contenu
            content = self.scraper.fetch_profile_content(profile.url)
            if not content:
                profile.error_count += 1
                print(f"❌ Impossible de récupérer le contenu")
                return None
            
            # Extraire le hash et détecter les nouveaux posts
            current_hash, new_post = ContentExtractor.extract_activity_hash(content, profile.name)
            
            print(f"📊 Hash actuel: {current_hash}")
            print(f"📊 Hash précédent: {profile.last_hash}")
            
            # Vérifier les changements
            if profile.last_hash != current_hash:
                print(f"🆕 CHANGEMENT DÉTECTÉ!")
                profile.last_hash = current_hash
                profile.error_count = 0  # Reset errors on success
                self.stats['changes'] += 1
                
                if new_post:
                    print(f"📝 Nouveau post détecté: {new_post.title[:50]}...")
                    self.stats['new_posts'] += 1
                    return new_post
            else:
                print("⚪ Aucun changement")
                profile.error_count = 0  # Reset errors on success
            
            return None
            
        except Exception as e:
            print(f"❌ Erreur vérification {profile.name}: {e}")
            profile.error_count += 1
            return None
    
    def run(self) -> bool:
        """Lance le monitoring complet"""
        try:
            print("=" * 80)
            print("🚀 LINKEDIN MONITORING - Version Corrigée")
            print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S UTC')}")
            print("=" * 80)
            
            # Configuration email
            if not self.setup_email():
                print("❌ Configuration email échouée")
                return False
            
            # Chargement des profils
            profiles = CSVManager.load_profiles(self.csv_file)
            if not profiles:
                print("❌ Aucun profil à surveiller")
                return False
            
            self.stats['total'] = len(profiles)
            new_posts = []
            changes_made = False
            
            # Vérification de chaque profil
            for i, profile in enumerate(profiles):
                try:
                    print(f"\n--- PROFIL {i+1}/{len(profiles)} ---")
                    
                    new_post = self.check_profile(profile)
                    
                    if new_post:
                        new_posts.append(new_post)
                        changes_made = True
                    
                    self.stats['success'] += 1
                    
                except Exception as e:
                    print(f"❌ Erreur traitement profil {i+1}: {e}")
                    self.stats['errors'] += 1
                
                # Pause entre les profils pour éviter le rate limiting
                if i < len(profiles) - 1:
                    pause = 15 + (i % 3) * 5  # 15-25 secondes
                    print(f"⏳ Pause {pause}s...")
                    time.sleep(pause)
            
            # Sauvegarde si changements
            if changes_made:
                CSVManager.save_profiles(self.csv_file, profiles)
                print("\n💾 Profils sauvegardés")
            
            # Envoi des notifications
            if new_posts:
                print(f"\n📧 Envoi notification pour {len(new_posts)} nouveau(x) post(s)...")
                if self.notifier.send_notification(new_posts):
                    print("✅ Notifications envoyées")
                else:
                    print("❌ Erreur envoi notifications")
            else:
                print("\n📭 Aucun nouveau post détecté")
            
            # Rapport final
            self._print_final_report()
            
            return self.stats['success'] > 0
            
        except Exception as e:
            print(f"💥 ERREUR CRITIQUE: {e}")
            traceback.print_exc()
            return False
    
    def _print_final_report(self):
        """Affiche le rapport final"""
        print("\n" + "=" * 80)
        print("📊 RAPPORT FINAL")
        print("=" * 80)
        print(f"📋 Profils traités: {self.stats['success']}/{self.stats['total']}")
        print(f"🆕 Changements détectés: {self.stats['changes']}")
        print(f"📝 Nouveaux posts: {self.stats['new_posts']}")
        print(f"❌ Erreurs: {self.stats['errors']}")
        
        success_rate = (self.stats['success'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        print(f"📈 Taux de succès: {success_rate:.1f}%")
        print("=" * 80)


def main():
    """Point d'entrée principal"""
    try:
        # Lancement du monitoring
        monitor = LinkedInMonitor()
        success = monitor.run()
        
        if success:
            print("\n🎉 MONITORING TERMINÉ AVEC SUCCÈS")
            sys.exit(0)
        else:
            print("\n💥 ÉCHEC DU MONITORING")
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
