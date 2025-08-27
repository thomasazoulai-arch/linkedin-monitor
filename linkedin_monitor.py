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

class LinkedInMonitor:
    def __init__(self, csv_file_path, email_config):
        self.csv_file_path = csv_file_path
        self.email_config = email_config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        print(f"✅ LinkedInMonitor initialisé")
    
    def load_urls_from_csv(self):
        """Charge les URLs depuis le fichier CSV"""
        try:
            print(f"📁 Chargement du fichier: {self.csv_file_path}")
            
            if not os.path.exists(self.csv_file_path):
                print(f"❌ Fichier {self.csv_file_path} introuvable")
                print("📂 Fichiers présents:")
                for file in os.listdir('.'):
                    print(f"   - {file}")
                return None
            
            data = []
            with open(self.csv_file_path, 'r', encoding='utf-8', newline='') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
            
            print(f"✅ {len(data)} lignes chargées")
            
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
            
            with open(self.csv_file_path, 'w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            print("✅ Fichier sauvegardé")
            return True
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def scrape_linkedin_profile(self, url, profile_name):
        """Scrape simple d'une page LinkedIn"""
        try:
            print(f"🌐 Vérification de {profile_name}...")
            
            time.sleep(3)
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                # Génère un ID basé sur le contenu
                content_sample = response.text[:3000]
                post_id = hashlib.md5(content_sample.encode('utf-8', errors='ignore')).hexdigest()[:12]
                
                print(f"✅ ID généré: {post_id}")
                return {
                    'id': post_id,
                    'profile': profile_name,
                    'timestamp': datetime.now().isoformat(),
                    'content': f"Contenu détecté pour {profile_name}"
                }
            else:
                print(f"❌ HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur scraping: {e}")
            return None
    
    def send_simple_email(self, post_info):
        """Envoi d'email ultra-simplifié"""
        try:
            print(f"📧 Envoi email...")
            
            sender_email = self.email_config['sender_email']
            sender_password = self.email_config['sender_password']
            recipient_email = self.email_config['recipient_email']
            
            # Construction manuelle du message email
            subject = f"Veille LinkedIn - {post_info['profile']}"
            body = f"""Nouveau changement detecte sur LinkedIn !

Profil: {post_info['profile']}
Detecte le: {datetime.fromisoformat(post_info['timestamp']).strftime('%d/%m/%Y a %H:%M')}
ID: {post_info['id']}

---
Systeme de veille automatise
"""
            
            # Message au format RFC 2822 simple
            message = f"""From: {sender_email}
To: {recipient_email}
Subject: {subject}
Content-Type: text/plain; charset=utf-8

{body}"""
            
            # Envoi via SMTP
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, [recipient_email], message.encode('utf-8'))
            
            print("✅ Email envoyé")
            return True
            
        except Exception as e:
            print(f"❌ Erreur email: {e}")
            traceback.print_exc()
            return False
    
    def check_for_new_posts(self):
        """Vérification des nouveaux posts"""
        try:
            print(f"🚀 DÉBUT - {datetime.now()}")
            
            data = self.load_urls_from_csv()
            if data is None:
                return False
            
            changes_made = False
            
            for i, row in enumerate(data):
                url = row.get('URL', '').strip()
                name = row.get('Name', '').strip()
                last_id = row.get('Last_Post_ID', '').strip()
                
                if not url or not name:
                    continue
                
                print(f"\n--- {i+1}/{len(data)}: {name} ---")
                
                result = self.scrape_linkedin_profile(url, name)
                
                if result:
                    current_id = result['id']
                    
                    if last_id != current_id:
                        print(f"🆕 CHANGEMENT détecté!")
                        
                        if self.send_simple_email(result):
                            row['Last_Post_ID'] = current_id
                            changes_made = True
                            print("✅ Notification envoyée")
                    else:
                        print("⚪ Aucun changement")
                
                if i < len(data) - 1:
                    time.sleep(5)
            
            if changes_made:
                self.save_urls_to_csv(data)
                print("💾 Données sauvegardées")
            
            print(f"🏁 FIN - {datetime.now()}")
            return True
            
        except Exception as e:
            print(f"❌ ERREUR: {e}")
            traceback.print_exc()
            return False

def main():
    try:
        print("🔧 === DÉMARRAGE ===")
        
        csv_file = "linkedin_urls.csv"
        
        email_config = {
            'sender_email': os.getenv('GMAIL_EMAIL'),
            'sender_password': os.getenv('GMAIL_APP_PASSWORD'),
            'recipient_email': os.getenv('RECIPIENT_EMAIL')
        }
        
        print(f"📧 Sender: {email_config['sender_email']}")
        print(f"📧 Recipient: {email_config['recipient_email']}")
        print(f"🔑 Password configured: {'Yes' if email_config['sender_password'] else 'No'}")
        
        missing_vars = [key for key, value in email_config.items() if not value]
        if missing_vars:
            print(f"❌ Variables manquantes: {missing_vars}")
            sys.exit(1)
        
        monitor = LinkedInMonitor(csv_file, email_config)
        success = monitor.check_for_new_posts()
        
        if success:
            print("✅ SUCCESS")
            sys.exit(0)
        else:
            print("❌ FAILED")
            sys.exit(1)
        
    except Exception as e:
        print(f"❌ ERREUR FATALE: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
