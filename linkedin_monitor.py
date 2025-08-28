import requests
import csv
import json
import time
from datetime import datetime
import os
import re
import hashlib
import smtplib
import sys
import traceback

# Import email modules with fallback
try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_LIBS_AVAILABLE = True
except ImportError:
    print("⚠️ Email libraries not available, using simple SMTP")
    EMAIL_LIBS_AVAILABLE = False

class LinkedInMonitor:
    def __init__(self, csv_file_path, email_config):
        self.csv_file_path = csv_file_path
        self.email_config = email_config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        print(f"✅ LinkedInMonitor initialisé")
    
    def create_default_csv(self):
        """Crée un fichier CSV par défaut s'il n'existe pas"""
        try:
            print("📝 Création d'un fichier CSV par défaut")
            
            default_data = [
                {
                    'URL': 'https://www.linkedin.com/company/microsoft/',
                    'Name': 'Microsoft',
                    'Last_Post_ID': ''
                },
                {
                    'URL': 'https://www.linkedin.com/company/tesla-motors/',
                    'Name': 'Tesla',
                    'Last_Post_ID': ''
                }
            ]
            
            fieldnames = ['URL', 'Name', 'Last_Post_ID']
            
            with open(self.csv_file_path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(default_data)
            
            print("✅ Fichier CSV créé avec les données par défaut")
            return default_data
            
        except Exception as e:
            print(f"❌ Erreur création CSV: {e}")
            return None

    def load_urls_from_csv(self):
        """Charge les URLs depuis le fichier CSV - MÉTHODE CORRIGÉE"""
        try:
            print(f"📁 Chargement du fichier: {self.csv_file_path}")
            
            if not os.path.exists(self.csv_file_path):
                print(f"❌ Fichier {self.csv_file_path} introuvable")
                print("📂 Création d'un fichier par défaut...")
                return self.create_default_csv()
            
            data = []
            
            # Essaie plusieurs encodages
            encodings = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252', 'latin1']
            
            for encoding in encodings:
                try:
                    print(f"🔄 Tentative avec encodage: {encoding}")
                    with open(self.csv_file_path, 'r', encoding=encoding, newline='') as file:
                        reader = csv.DictReader(file)
                        for row in reader:
                            data.append(row)
                    print(f"✅ Succès avec {encoding} - {len(data)} lignes chargées")
                    break
                except UnicodeDecodeError:
                    print(f"❌ Échec avec {encoding}")
                    data = []
                    continue
            
            if not data:
                print("❌ Impossible de lire le fichier avec tous les encodages testés")
                print("📂 Création d'un fichier par défaut...")
                return self.create_default_csv()
            
            # Ajouter Last_Post_ID si manquant
            for row in data:
                if 'Last_Post_ID' not in row:
                    row['Last_Post_ID'] = ''
            
            return data
            
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            traceback.print_exc()
            return None
    
    def save_urls_to_csv(self, data):
        """Sauvegarde le fichier CSV"""
        try:
            print("💾 Sauvegarde...")
            
            if not data:
                return False
            
            fieldnames = list(data[0].keys())
            
            # Sauvegarde avec encodage UTF-8 et BOM pour compatibilité
            with open(self.csv_file_path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            print("✅ Fichier sauvegardé en UTF-8")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def extract_content_info(self, html_content):
        """Extrait des informations du contenu HTML LinkedIn"""
        try:
            # Recherche de patterns spécifiques LinkedIn
            patterns = {
                'post_activity': r'<span[^>]*>(\d+)\s*(comments?|likes?|reactions?)',
                'company_updates': r'posted this',
                'profile_activity': r'activity-[a-zA-Z0-9]+',
                'content_hash': r'data-urn="[^"]*"'
            }
            
            info = {
                'has_recent_activity': False,
                'activity_indicators': [],
                'content_snippets': []
            }
            
            for pattern_name, pattern in patterns.items():
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    info['has_recent_activity'] = True
                    info['activity_indicators'].append(pattern_name)
            
            # Extrait quelques snippets de contenu
            text_patterns = [
                r'<span[^>]*class="[^"]*feed-shared-text[^"]*"[^>]*>([^<]+)</span>',
                r'<h3[^>]*>([^<]+)</h3>',
                r'<p[^>]*>([^<]+)</p>'
            ]
            
            for pattern in text_patterns:
                matches = re.findall(pattern, html_content)
                info['content_snippets'].extend(matches[:3])  # Limite à 3 snippets
            
            return info
            
        except Exception as e:
            print(f"❌ Erreur extraction contenu: {e}")
            return {'has_recent_activity': False, 'activity_indicators': [], 'content_snippets': []}
    
    def scrape_linkedin_profile(self, url, profile_name):
        """Scrape amélioré d'une page LinkedIn"""
        try:
            print(f"🌐 Vérification de {profile_name}...")
            
            # Pause pour éviter les limitations
            time.sleep(5)
            
            # Ajout de paramètres pour les pages company
            if 'company' in url and 'posts' not in url:
                if not url.endswith('/'):
                    url += '/'
                url += 'posts/'
            
            response = requests.get(url, headers=self.headers, timeout=20)
            
            if response.status_code == 200:
                print(f"✅ Page accessible ({len(response.text)} caractères)")
                
                # Extraction d'informations du contenu
                content_info = self.extract_content_info(response.text)
                
                # Génère un ID basé sur le contenu significatif
                content_for_hash = response.text[:5000]  # Plus de contenu pour l'ID
                
                # Ajoute les indicateurs d'activité à l'ID
                activity_string = ''.join(content_info['activity_indicators'])
                snippets_string = ''.join(content_info['content_snippets'][:5])
                
                hash_content = content_for_hash + activity_string + snippets_string
                post_id = hashlib.sha256(hash_content.encode('utf-8', errors='ignore')).hexdigest()[:16]
                
                print(f"✅ ID généré: {post_id}")
                print(f"📊 Activité détectée: {content_info['has_recent_activity']}")
                
                return {
                    'id': post_id,
                    'profile': profile_name,
                    'url': url,
                    'timestamp': datetime.now().isoformat(),
                    'content_info': content_info,
                    'status': 'success'
                }
            else:
                print(f"❌ HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur scraping: {e}")
            return None
    
    def send_email_notification(self, post_info):
        """Envoi d'email de notification avec fallback"""
        try:
            print(f"📧 Préparation email pour {post_info['profile']}...")
            
            sender_email = self.email_config['sender_email']
            sender_password = self.email_config['sender_password']
            recipient_email = self.email_config['recipient_email']
            
            # Construction du corps du message
            timestamp_fr = datetime.fromisoformat(post_info['timestamp']).strftime('%d/%m/%Y à %H:%M')
            
            subject = f"🔔 Nouveau contenu LinkedIn - {post_info['profile']}"
            
            body = f"""Bonjour,

Un nouveau contenu a été détecté sur LinkedIn !

🏢 Profil/Entreprise : {post_info['profile']}
🔗 URL : {post_info['url']}
📅 Détecté le : {timestamp_fr}
🆔 ID de suivi : {post_info['id']}

📊 Informations détectées :
• Activité récente : {'Oui' if post_info['content_info']['has_recent_activity'] else 'Non'}
• Indicateurs : {', '.join(post_info['content_info']['activity_indicators']) if post_info['content_info']['activity_indicators'] else 'Aucun'}

---
✨ Système de veille LinkedIn automatisé
🤖 Propulsé par votre agent autonome

Pour consulter le contenu, cliquez sur le lien ci-dessus.
"""
            
            if EMAIL_LIBS_AVAILABLE:
                # Méthode avec MimeMultipart (préférée)
                message = MimeMultipart()
                message["Subject"] = subject
                message["From"] = sender_email
                message["To"] = recipient_email
                message.attach(MimeText(body, "plain", "utf-8"))
                msg_string = message.as_string()
            else:
                # Méthode manuelle simple (fallback)
                msg_string = f"""From: {sender_email}
To: {recipient_email}
Subject: {subject}
Content-Type: text/plain; charset=utf-8

{body}"""
            
            # Envoi via Gmail SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                if EMAIL_LIBS_AVAILABLE:
                    server.sendmail(sender_email, recipient_email, msg_string)
                else:
                    server.sendmail(sender_email, recipient_email, msg_string.encode('utf-8'))
            
            print("✅ Email envoyé avec succès")
            return True
            
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            traceback.print_exc()
            return False
    
    def check_for_new_posts(self):
        """Vérification des nouveaux posts - VERSION CORRIGÉE"""
        try:
            print(f"🚀 DÉBUT DU MONITORING - {datetime.now()}")
            
            # Chargement des données
            data = self.load_urls_from_csv()  # Cette méthode existe maintenant !
            if data is None:
                print("❌ Impossible de charger les données")
                return False
            
            changes_made = False
            successful_checks = 0
            
            print(f"📋 {len(data)} profils à vérifier")
            
            for i, row in enumerate(data):
                url = row.get('URL', '').strip()
                name = row.get('Name', '').strip()
                last_id = row.get('Last_Post_ID', '').strip()
                
                if not url or not name:
                    print(f"⚠️ Ligne {i+1} ignorée (URL ou nom manquant)")
                    continue
                
                print(f"\n--- {i+1}/{len(data)}: {name} ---")
                print(f"🔗 URL: {url}")
                print(f"🆔 Dernier ID: {last_id if last_id else 'Aucun'}")
                
                # Scraping de la page
                result = self.scrape_linkedin_profile(url, name)
                
                if result and result['status'] == 'success':
                    successful_checks += 1
                    current_id = result['id']
                    
                    print(f"🔍 ID actuel: {current_id}")
                    
                    # Vérification des changements
                    if last_id != current_id:
                        print(f"🆕 CHANGEMENT DÉTECTÉ pour {name}!")
                        
                        # Envoi de notification
                        if self.send_email_notification(result):
                            row['Last_Post_ID'] = current_id
                            changes_made = True
                            print("✅ Notification envoyée et ID mis à jour")
                        else:
                            print("❌ Échec envoi notification")
                    else:
                        print("⚪ Aucun changement détecté")
                else:
                    print(f"❌ Échec vérification de {name}")
                
                # Pause entre les vérifications (sauf pour le dernier)
                if i < len(data) - 1:
                    print("⏳ Pause de 8 secondes...")
                    time.sleep(8)
            
            # Sauvegarde des modifications
            if changes_made:
                if self.save_urls_to_csv(data):
                    print("💾 Données sauvegardées avec succès")
                else:
                    print("❌ Échec sauvegarde")
            
            # Résumé
            print(f"\n📊 RÉSUMÉ:")
            print(f"✅ Vérifications réussies: {successful_checks}/{len(data)}")
            print(f"📝 Changements détectés: {'Oui' if changes_made else 'Non'}")
            print(f"🏁 FIN - {datetime.now()}")
            
            return True
            
        except Exception as e:
            print(f"❌ ERREUR CRITIQUE: {e}")
            traceback.print_exc()
            return False

def main():
    try:
        print("=" * 50)
        print("🔧 AGENT LINKEDIN - DÉMARRAGE")
        print("=" * 50)
        
        # Configuration
        csv_file = "linkedin_urls.csv"
        
        # Variables d'environnement
        email_config = {
            'sender_email': os.getenv('GMAIL_EMAIL'),
            'sender_password': os.getenv('GMAIL_APP_PASSWORD'),
            'recipient_email': os.getenv('RECIPIENT_EMAIL')
        }
        
        # Vérification configuration
        print(f"📧 Email expéditeur: {email_config['sender_email']}")
        print(f"📧 Email destinataire: {email_config['recipient_email']}")
        print(f"🔑 Mot de passe configuré: {'Oui' if email_config['sender_password'] else 'Non'}")
        
        # Vérification variables manquantes
        missing_vars = [key for key, value in email_config.items() if not value]
        if missing_vars:
            print(f"❌ Variables d'environnement manquantes: {missing_vars}")
            print("💡 Assurez-vous que GMAIL_EMAIL, GMAIL_APP_PASSWORD et RECIPIENT_EMAIL sont définies")
            sys.exit(1)
        
        # Initialisation et lancement
        monitor = LinkedInMonitor(csv_file, email_config)
        success = monitor.check_for_new_posts()
        
        if success:
            print("✅ MONITORING TERMINÉ AVEC SUCCÈS")
            sys.exit(0)
        else:
            print("❌ ÉCHEC DU MONITORING")
            sys.exit(1)
        
    except Exception as e:
        print(f"💥 ERREUR FATALE: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
